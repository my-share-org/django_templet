from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class HealthThrottle(AnonRateThrottle):
    scope = "health"


class AuthenticatedUserRateThrottle(SimpleRateThrottle):
    """
    Throttles strictly authenticated users, keyed by request.user.pk.
    Returns None for unauthenticated callers so it safely bypasses anonymous requests,
    allowing independent AnonRateThrottle to handle anonymous traffic.
    """
    scope = "user"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class TargetIdentifierRateThrottle(SimpleRateThrottle):
    """
    Target-based / trigger-based rate throttle keyed on the recipient identifier
    (email, phone number, or username) rather than client IP.
    
    Protects against:
    - Distributed email/SMS bombing and victim harassment (where attackers rotate IPs).
    - Distributed credential stuffing against a specific target account.
    """
    scope = "target_identifier"

    def get_rate(self):
        try:
            return super().get_rate()
        except Exception:
            return "60/min"

    def get_target_identifier(self, request, view):
        """
        Extract the target identifier from request data or authenticated user.
        """
        data = getattr(request, "data", {})
        if isinstance(data, dict):
            for field in ("user_identifier", "email", "identifier", "username"):
                value = data.get(field)
                if value and isinstance(value, str):
                    return value.strip().lower()

        # If unprovided in data and caller is logged in, use their email or PK
        if getattr(request, "user", None) and request.user.is_authenticated:
            email = getattr(request.user, "email", None)
            if email:
                return str(email).strip().lower()
            return str(request.user.pk)

        return None

    def get_cache_key(self, request, view):
        ident = self.get_target_identifier(request, view)
        if not ident:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
