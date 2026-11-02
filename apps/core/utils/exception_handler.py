from django.http import JsonResponse
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler

from apps.core.utils.response import error_response


def _friendly_message(exc: APIException) -> str:
    if isinstance(exc, ValidationError):
        return "Validation failed."
    if isinstance(exc, NotAuthenticated):
        return "Authentication credentials were not provided."
    if isinstance(exc, AuthenticationFailed):
        return "Authentication failed."
    if isinstance(exc, PermissionDenied):
        return "You do not have permission to perform this action."
    if isinstance(exc, NotFound):
        return "The requested resource was not found."
    if isinstance(exc, MethodNotAllowed):
        return "Method not allowed."
    if isinstance(exc, Throttled):
        wait = getattr(exc, "wait", None)
        if wait:
            return f"Too many requests. Try again in {int(wait)} second(s)."
        return "Too many requests."
    return "An error occurred."


def _extract_field_errors(data: dict) -> dict | None:
    """
    Return field-level errors only when real field keys are present.
    {"detail": "..."} is a non-field error — message alone is sufficient.
    """
    if not isinstance(data, dict) or list(data.keys()) == ["detail"]:
        return None
    return {
        field: [str(m) for m in (msgs if isinstance(msgs, list) else [msgs])]
        for field, msgs in data.items()
    } or None


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return error_response(
            message="Internal server error.",
            status_code=500,
            exc=exc,
        )

    errors = _extract_field_errors(response.data) if isinstance(exc, ValidationError) else None

    return error_response(
        message=_friendly_message(exc),
        errors=errors,
        status_code=response.status_code,
        exc=exc,
    )


def handle_404(request, exception=None):
    r = error_response(
        message="The requested endpoint does not exist.",
        status_code=404,
    )
    return JsonResponse(r.data, status=404)


def handle_500(request):
    r = error_response(
        message="Internal server error.",
        status_code=500,
    )
    return JsonResponse(r.data, status=500)
