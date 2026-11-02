import traceback

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response


def _normalize_errors(errors) -> dict | list | None:
    if errors is None:
        return None

    if isinstance(errors, dict):
        return {
            field: [str(m) for m in (msgs if isinstance(msgs, list) else [msgs])]
            for field, msgs in errors.items()
        }

    if isinstance(errors, (list, tuple)):
        return [str(e) for e in errors]

    if isinstance(errors, DjangoValidationError):
        if hasattr(errors, "message_dict"):
            return _normalize_errors(errors.message_dict)
        return errors.messages

    if isinstance(errors, APIException):
        return _normalize_errors(errors.detail)

    return [str(errors)]


def success_response(message="Success", data=None, status_code=status.HTTP_200_OK):
    return Response(
        {"success": True, "message": message, "data": data},
        status=status_code,
    )


def error_response(
    *,
    message: str = "Something went wrong.",
    errors=None,
    data=None,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    request=None,
    exc: Exception | None = None,
):
    payload = {
        "success": False,
        "message": message,
        "data": data,
        "errors": _normalize_errors(errors),
    }

    # exc is the raw exception for debug tracing (separate from user-facing errors)
    debug_target = exc if exc is not None else (errors if isinstance(errors, Exception) else None)
    if settings.DEBUG and debug_target is not None:
        extra = {
            "exception": debug_target.__class__.__name__,
            "traceback": traceback.format_exc(),
        }
        if request is not None:
            extra["path"] = request.path
            extra["method"] = request.method
            extra["payload"] = request.GET if request.method == "GET" else getattr(request, "data", None)
        payload["debug"] = extra

    return Response(payload, status=status_code)
