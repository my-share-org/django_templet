from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.utils.general import get_or_400
from apps.core.utils.response import error_response
from apps.core.utils.validators import validate_phone
from apps.otp.choices import OtpChannel, OtpPurpose

User = get_user_model()

config = settings.CONFIG


@dataclass(frozen=True)
class OTPPolicy:
    enable: bool              # Is OTP enabled for this purpose?
    require_auth: bool        # Must the caller be authenticated?
    require_identifier: bool  # Must the client supply user_identifier?
    check_user_exists: bool   # Must a matching user already exist?
    allow_duplicate: bool     # May a matching user already exist?
    channel: OtpChannel = OtpChannel(config.OTP_CHANNEL)  # Allowed OTP channel


# Field order matches OTPPolicy: positional args line up with the header row.
_OTP_POLICY_TABLE: dict[str, OTPPolicy] = {
    #                                       Enabled  Req_Auth  Req_Identifier  User_Exists  Allow_Duplicate
    OtpPurpose.LOGIN:            OTPPolicy( False,   False,    True,            True,        True),
    OtpPurpose.REGISTRATION:     OTPPolicy( True,    False,    True,            False,       False),
    OtpPurpose.PASSWORD_CHANGE:  OTPPolicy( False,   True,     False,           True,        True),
    OtpPurpose.PASSWORD_RESET:   OTPPolicy( True,    False,    True,            True,        True),
    OtpPurpose.CHANGE_EMAIL:     OTPPolicy( True,    True,     False,           True,        True),
    OtpPurpose.CHANGE_PHONE:     OTPPolicy( False,   True,     False,           True,        True),
    OtpPurpose.CHANGE_USERNAME:  OTPPolicy( False,   True,     False,           True,        True),
    OtpPurpose.VERIFICATION:     OTPPolicy( False,   True,     False,           True,        True),
}


def get_otp_rules(purpose: OtpPurpose) -> OTPPolicy:
    policy = _OTP_POLICY_TABLE.get(purpose)
    if policy is None:
        raise ValueError(f"Invalid OTP purpose: {purpose}")
    return policy


def verify_otp_rules(request: Request) -> tuple[bool, Response | dict]:
    """
    Validate an OTP request against the policy registered for its purpose.

    Returns (False, Response) with a ready-to-return error response when any
    rule fails, or (True, {"user_identifier", "purpose", "otp_channel"}) when
    every rule passes.
    """
    if not isinstance(request.data, dict):
        return False, error_response(
            message="Invalid request data format",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ok, data = get_or_400(
        data=request.data,
        keys={
            "purpose": str,
            "user_identifier": str,
            "otp_channel": str,
            "region": str,
        },
        required=["purpose"],
    )
    if not ok:
        return False, data

    try:
        purpose = OtpPurpose(data["purpose"])
        otp_rules = get_otp_rules(purpose)
    except ValueError:
        return False, error_response(
            message='"purpose" must be a valid value',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # ============================
    # Rule 1: Enabled
    # ============================
    if not otp_rules.enable:
        return False, error_response(
            message=f"OTP is not enabled for {purpose.label} purpose",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # ============================
    # Rule 2: Authentication
    # ============================
    if otp_rules.require_auth and not request.user.is_authenticated:
        return False, error_response(
            message="Authentication required for this OTP purpose",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # ---------------------------
    # Pre-Required: Channel resolution
    # ---------------------------
    # The policy channel wins; the client may pick one only when the policy allows every channel (ALL).
    otp_channel = otp_rules.channel
    if otp_channel == OtpChannel.ALL:
        otp_channel = data.get("otp_channel")
        if not otp_channel:
            return False, error_response(
                message='"otp_channel" is required',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    if otp_channel not in (OtpChannel.EMAIL, OtpChannel.PHONE):
        return False, error_response(
            message=f'{otp_channel}: "otp_channel" is not valid',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # ============================
    # Rule 3: Identifier resolution
    # ============================
    # Purposes with require_identifier=False are, by definition, scoped to
    # "whoever is authenticated" — a client-supplied user_identifier must
    # never override that, or an authenticated caller could direct an
    # auth-required OTP (e.g. change_email) at someone else's identifier.
    if otp_rules.require_identifier:
        user_identifier = data.get("user_identifier")
        if not user_identifier:
            return False, error_response(
                message='"user_identifier" is required for this OTP purpose',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    elif request.user.is_authenticated:
        user_identifier = (
            request.user.email
            if otp_channel == OtpChannel.EMAIL
            else getattr(request.user, "phone", None)
        )
    else:
        user_identifier = None

    if not user_identifier:
        return False, error_response(
            message="Could not determine user identifier",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------
    # Post required validation: Identifier format
    # ---------------------------------------------
    try:
        if otp_channel == OtpChannel.EMAIL:
            validate_email(user_identifier)
        else:
            region = data.get("region")
            if not region:
                return False, error_response(
                    message='"region" is required for phone OTP',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            validate_phone(user_identifier, region)
    except ValidationError as e:
        return False, error_response(
            message="Invalid user identifier",
            errors=e,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # ==========================================
    # Rule 4 & 5: User existence / duplication
    # ==========================================
    # A lookup is needed both when a user must exist (check_user_exists) and
    # when one must NOT already exist (allow_duplicate=False, e.g. registration).
    if otp_rules.check_user_exists or not otp_rules.allow_duplicate:
        if request.user.is_authenticated:
            user = request.user
        else:
            filter_field = "email" if otp_channel == OtpChannel.EMAIL else "phone"
            user = User.objects.filter(**{filter_field: user_identifier}).first()

        if otp_rules.check_user_exists and user is None:
            return False, error_response(
                message="User not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if not otp_rules.allow_duplicate and user is not None:
            return False, error_response(
                message="User already exists",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    return True, {
        "user_identifier": user_identifier,
        "purpose": purpose,
        "otp_channel": otp_channel,
    }
