import uuid
import hmac
from typing import Optional
from datetime import timedelta

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
from rest_framework.exceptions import ValidationError
import hashlib

from core.cache.redis_client import redis_client
from core.utils.generators import random_string
from otp.choices import OtpPurpose, OtpChannel
from emails.tasks import send_email_task
from emails.choices import EmailBodyType

CONFIG = settings.CONFIG


class OTPService:
    """
    Secure Redis-backed OTP service.

    - Max 5 active OTPs per user per purpose
    - OTP TTL: 5 minutes
    - One-time use
    - OTP stored hashed
    """

    OTP_TTL_SECONDS = CONFIG.OTP_EXPIRY_MINUTES * 60
    MAX_ACTIVE_OTPS = CONFIG.MAX_ACTIVE_OTPS
    MAX_VERIFY_ATTEMPTS = CONFIG.MAX_VERIFY_ATTEMPTS

    @staticmethod
    def _user_hash(user: str) -> str:
        """Return SHA256 hash of user identifier."""
        return hashlib.sha256(user.encode()).hexdigest()

    @staticmethod
    def _hash_otp(otp: str) -> str:
        """Hash OTP before storing using HMAC-SHA256 with project SECRET_KEY."""
        return hmac.new(
            settings.SECRET_KEY.encode(),
            otp.encode(),
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    def _otp_key(cls, purpose: OtpPurpose, user_hash: str, otp_id: str) -> str:
        """Redis key for a specific OTP."""
        return f"otp:{purpose}:{user_hash}:{otp_id}"

    @classmethod
    def _index_key(cls, purpose: OtpPurpose, user_hash: str) -> str:
        """Redis key storing active OTP ids."""
        return f"otp:index:{purpose}:{user_hash}"

    @classmethod
    def _attempts_key(cls, purpose: OtpPurpose, user_hash: str) -> str:
        """Redis key tracking failed verify attempts for a lockout window."""
        return f"otp:attempts:{purpose}:{user_hash}"

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    @classmethod
    def generate(cls, user: str, purpose: OtpPurpose) -> str:
        """
        Generate and store a new OTP.

        A new OTP request automatically invalidates any previously active OTP
        for the same user and purpose, preventing multiple active codes.
        """

        user_hash = cls._user_hash(user)
        index_key = cls._index_key(purpose, user_hash)

        # Invalidate any previously generated active OTPs for this user and purpose
        existing_otp_ids = redis_client.lrange(index_key, 0, -1)
        if existing_otp_ids:
            pipe_cleanup = redis_client.pipeline()
            for existing_id in existing_otp_ids:
                pipe_cleanup.delete(cls._otp_key(purpose, user_hash, existing_id))
            pipe_cleanup.delete(index_key)
            pipe_cleanup.delete(cls._attempts_key(purpose, user_hash))
            pipe_cleanup.execute()

        otp = random_string(
            length=CONFIG.OTP_LENGTH,
            allow_numbers=CONFIG.OTP_ALLOW_NUMBER,
            allow_capital=CONFIG.OTP_ALLOW_CAPITAL,
            allow_small=CONFIG.OTP_ALLOW_SMALL,
            allow_special=CONFIG.OTP_ALLOW_SPECIAL,
        )
        otp_hash = cls._hash_otp(otp)
        otp_id = str(uuid.uuid4())

        otp_key = cls._otp_key(purpose, user_hash, otp_id)

        pipe = redis_client.pipeline()

        # Store OTP with TTL
        pipe.set(otp_key, otp_hash, ex=cls.OTP_TTL_SECONDS)

        # Push OTP id to index list
        pipe.rpush(index_key, otp_id)
        pipe.expire(index_key, cls.OTP_TTL_SECONDS)

        pipe.execute()

        return otp

    @classmethod
    def verify(cls, user: str, purpose: OtpPurpose, submitted_otp: str) -> bool:
        """
        Verify OTP against active ones.

        Deletes OTP on successful match. Locks out further attempts for
        this user+purpose once MAX_VERIFY_ATTEMPTS is exceeded within the
        OTP's TTL window, so a valid OTP can't be brute-forced by guessing
        (6-digit numeric OTPs are only ~1M possibilities).
        """

        user_hash = cls._user_hash(user)
        index_key = cls._index_key(purpose, user_hash)
        attempts_key = cls._attempts_key(purpose, user_hash)

        attempts = redis_client.incr(attempts_key)
        if attempts == 1:
            redis_client.expire(attempts_key, cls.OTP_TTL_SECONDS)
        if attempts > cls.MAX_VERIFY_ATTEMPTS:
            return False

        otp_ids = redis_client.lrange(index_key, 0, -1)

        submitted_hash = cls._hash_otp(submitted_otp)

        for otp_id in otp_ids:
            otp_key = cls._otp_key(purpose, user_hash, otp_id)
            stored_hash = redis_client.get(otp_key)

            if not stored_hash:
                continue

            # Constant-time comparison
            if hmac.compare_digest(stored_hash, submitted_hash):
                cls._delete_otp(index_key, otp_key, otp_id)
                redis_client.delete(attempts_key)
                return True

        return False

    # ---------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------

    @classmethod
    def _delete_otp(cls, index_key: str, otp_key: str, otp_id: str) -> None:
        """Remove OTP from Redis and index."""
        pipe = redis_client.pipeline()
        pipe.delete(otp_key)
        pipe.lrem(index_key, 0, otp_id)
        pipe.execute()

    @classmethod
    def _enforce_limit(cls, index_key: str, purpose: OtpPurpose, user_hash: str) -> None:
        """Ensure only MAX_ACTIVE_OTPS are stored."""
        length = redis_client.llen(index_key)

        if length <= cls.MAX_ACTIVE_OTPS:
            return

        excess = length - cls.MAX_ACTIVE_OTPS

        for _ in range(excess):
            oldest_id = redis_client.lpop(index_key)
            if oldest_id:
                otp_key = cls._otp_key(purpose, user_hash, oldest_id)
                redis_client.delete(otp_key)

    @classmethod
    def send(cls, user: str, purpose: OtpPurpose, channel: OtpChannel) -> None:
        """Send OTP to user."""
        # Get OTP
        otp = cls.generate(user, purpose)
        match channel:
            case OtpChannel.EMAIL:
                rendered_body = render_to_string(
                    "otp_body.html",
                    {
                        "otp": otp,
                        "purpose": purpose,
                        "expiry_minutes": CONFIG.OTP_EXPIRY_MINUTES,
                    },
                )
                masked_body = render_to_string(
                    "otp_body.html",
                    {
                        "otp": "******",
                        "purpose": purpose,
                        "expiry_minutes": CONFIG.OTP_EXPIRY_MINUTES,
                    },
                )
                send_email_task.delay(
                    subject="OTP",
                    to_emails=[user],
                    body=rendered_body,
                    log_body=masked_body,
                    body_type=EmailBodyType.HTML,
                    purpose=purpose,
                )
            case OtpChannel.PHONE:
                raise ValidationError({"channel": ["SMS OTP delivery channel is not yet configured."]})
            case _:
                raise ValidationError({"channel": ["Invalid OTP channel."]})
    
