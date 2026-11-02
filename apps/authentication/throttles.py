from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from apps.core.throttles import TargetIdentifierRateThrottle


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class LoginTargetThrottle(TargetIdentifierRateThrottle):
    """
    Limits login attempts targeting a specific user account (by email/username).
    Prevents distributed credential stuffing across rotating IPs.
    """
    scope = "login_target"


class ChangePasswordThrottle(UserRateThrottle):
    scope = "change_password"


class ResetPasswordThrottle(AnonRateThrottle):
    scope = "reset_password"


class ResetPasswordTargetThrottle(TargetIdentifierRateThrottle):
    """
    Limits password reset attempts targeting a specific user account.
    """
    scope = "reset_password_target"
