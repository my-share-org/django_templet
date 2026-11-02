import traceback
from rest_framework.request import Request


def debug_error (errors: Exception | None = None):
    return {
        "exception": errors.__class__.__name__,
        # "error": _serialize_exception(errors),
        "traceback": traceback.format_exc(),
    }

def request_error (errors: Exception | None = None, request: Request | None = None):
    if request is not None:
        incoming = {
            "headers": dict(request.headers),
            "query_params": request.query_params,
            "data": request.data,
            "path": request.path,
            "method": request.method,
        }
    return {
        "incoming": incoming if request is not None else None,
        "error": debug_error(errors=errors),
    }