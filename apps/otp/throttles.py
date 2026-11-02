from rest_framework.throttling import AnonRateThrottle
from apps.core.throttles import AuthenticatedUserRateThrottle, TargetIdentifierRateThrottle


class OtpAnonRateThrottle(AnonRateThrottle):
    """
    Layer 1: IP-based throttle for anonymous callers.
    Limits a single IP from generating too many OTP requests across different targets.
    Automatically bypasses authenticated callers.
    """
    scope = "otp_anon"


class OtpUserRateThrottle(AuthenticatedUserRateThrottle):
    """
    Layer 2: User-based throttle for authenticated callers.
    Limits a logged-in user account from excessive OTP generation.
    Automatically bypasses anonymous callers.
    """
    scope = "otp_user"


class OtpTargetRateThrottle(TargetIdentifierRateThrottle):
    """
    Layer 3: Target recipient rate throttle.
    Limits OTP dispatch to a specific email/phone destination regardless of
    attacker IP rotation or anonymous/authenticated caller state.
    Prevents email/SMS bombing and victim harassment.
    """
    scope = "otp_target"


# Backward-compatibility alias
GetOtpRateThrottle = OtpUserRateThrottle
