import time
import logging

from django.conf import settings

from .services import record_activity, start_session

logger = logging.getLogger("django.logs.app")

_DEFAULT_SKIP_PATHS = ("/admin/", "/static/", "/media/", "/favicon.ico")


def _get_skip_paths():
    return tuple(getattr(settings, "ACTIVITY_SKIP_PATHS", _DEFAULT_SKIP_PATHS))


class ActivityTrackingMiddleware:
    """
    Must be registered AFTER logs.middleware.LoggingContextMiddleware so that
    request.request_id is already populated when process_response() fires.

    Responsibilities:
      - process_request:  resolve/create the user's session; record start time
      - process_response: dispatch record_activity() with the same request_id
                          SystemLog rows for this request carry, so the two
                          systems can be correlated at query time
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._process_request(request)
        response = self.get_response(request)
        return self._process_response(request, response)

    # ------------------------------------------------------------------ private

    def _process_request(self, request):
        request._activity_start_time = time.monotonic()
        request.activity_session = None
        try:
            if getattr(request, "user", None) and request.user.is_authenticated:
                request.activity_session = self._get_or_create_session(request)
        except Exception as exc:
            logger.warning(
                "ActivityTrackingMiddleware: session resolution failed: %s", exc,
                extra={"event_name": "activity.session.resolve_error"},
            )

    def _process_response(self, request, response):
        try:
            if not hasattr(request, "_activity_start_time"):
                return response

            if request.path.startswith(_get_skip_paths()):
                return response

            # If user authenticated during the view (e.g. via JWT authentication in DRF),
            # resolve or create the session now if it was not resolved during process_request.
            if getattr(request, "activity_session", None) is None:
                if (
                    getattr(request, "user", None)
                    and request.user.is_authenticated
                    and not getattr(request, "_session_ended", False)
                    and not request.path.rstrip("/").endswith("/logout")
                ):
                    try:
                        request.activity_session = self._get_or_create_session(request)
                    except Exception as exc:
                        logger.warning(
                            "ActivityTrackingMiddleware: session resolution failed in response: %s", exc,
                            extra={"event_name": "activity.session.resolve_error"},
                        )

            duration_ms = int((time.monotonic() - request._activity_start_time) * 1000)

            record_activity(
                request=request,
                response=response,
                session=request.activity_session,
                duration_ms=duration_ms,
                request_id=getattr(request, "request_id", None),
            )
        except Exception as exc:
            logger.warning(
                "ActivityTrackingMiddleware: process_response failed: %s", exc,
                extra={"event_name": "activity.middleware.response_error"},
            )
        return response

    def _get_or_create_session(self, request):
        from django.core.cache import cache
        from .models import UserSession

        user = request.user
        cache_key = f"activity:session:{user.pk}"

        session_key = cache.get(cache_key)
        if session_key:
            session = UserSession.objects.filter(
                session_key=session_key, is_active=True
            ).first()
            if session:
                return session

        session = (
            UserSession.objects.filter(user=user, is_active=True)
            .order_by("-started_at")
            .first()
        )
        if session is None:
            if getattr(request, "_session_ended", False) or request.path.rstrip("/").endswith("/logout"):
                return None
            session = start_session(user, request)

        if session:
            cache.set(cache_key, session.session_key, timeout=3600)
        return session
