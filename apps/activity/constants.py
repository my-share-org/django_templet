from .choices import ActivityAction

# Maps URL path prefixes to logical service names for UserActivity.service.
# Ordered longest-prefix-first so a more specific prefix never gets shadowed
# by a shorter one. "/" is the catch-all and must stay last.
# Add a new entry here whenever a new app/domain is introduced.
SERVICE_ROUTES: dict[str, str] = {
    "/v1/auth/":          "auth",
    "/v1/otp/":            "otp",
    "/v1/notifications/":  "notifications",
    "/":                   "core",
}

# Direct mapping from HTTP verb to a default ActivityAction.
HTTP_METHOD_TO_ACTION: dict[str, str] = {
    "GET":    ActivityAction.PAGE_VIEW,
    "POST":   ActivityAction.RESOURCE_CREATED,
    "PATCH":  ActivityAction.RESOURCE_UPDATED,
    "PUT":    ActivityAction.RESOURCE_UPDATED,
    "DELETE": ActivityAction.RESOURCE_DELETED,
}

# Path-specific overrides — checked before HTTP_METHOD_TO_ACTION.
# Keys are path substrings; first match wins.
PATH_ACTION_OVERRIDES: dict[str, str] = {
    "/v1/auth/login/":           ActivityAction.LOGIN,
    "/v1/auth/logout/":          ActivityAction.LOGOUT,
    "/v1/auth/token/refresh/":   ActivityAction.TOKEN_REFRESH,
    "/v1/auth/password/change/": ActivityAction.PASSWORD_CHANGE,
    "/v1/auth/password/reset/":  ActivityAction.PASSWORD_RESET,
    "/v1/otp/get-otp/":          ActivityAction.OTP_REQUESTED,
}


def resolve_service(path: str) -> str:
    """Return the service name for a request path.

    Iterates SERVICE_ROUTES (longest-prefix-first) and returns on first match.
    Falls back to "unknown" — should not happen since "/" is the catch-all.
    """
    for prefix, service in SERVICE_ROUTES.items():
        if path.startswith(prefix):
            return service
    return "unknown"


def resolve_action(method: str, path: str) -> str:
    """Return the ActivityAction for a given HTTP method + path.

    PATH_ACTION_OVERRIDES are checked first (substring match, first wins).
    Falls back to HTTP_METHOD_TO_ACTION keyed on the uppercased method.
    Falls back to ActivityAction.UNKNOWN if neither matches.
    """
    for fragment, action in PATH_ACTION_OVERRIDES.items():
        if fragment in path:
            return action

    if method.upper() == "GET" and "?q=" in path:
        return ActivityAction.SEARCH

    return HTTP_METHOD_TO_ACTION.get(method.upper(), ActivityAction.UNKNOWN)
