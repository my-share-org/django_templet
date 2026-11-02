import re
import uuid
import logging

from apps.core.utils.general import get_client_ip
from .choices import DeviceType
from .constants import resolve_action, resolve_service

logger = logging.getLogger("django.logs.app")

_MOBILE_RE = re.compile(r"mobi|android|iphone", re.IGNORECASE)
_TABLET_RE = re.compile(r"ipad|tablet", re.IGNORECASE)


def _detect_device_type(user_agent):
    if not user_agent:
        return DeviceType.UNKNOWN
    if _MOBILE_RE.search(user_agent):
        return DeviceType.MOBILE
    if _TABLET_RE.search(user_agent):
        return DeviceType.TABLET
    return DeviceType.DESKTOP


def _get_ip(request):
    return get_client_ip(request)


def start_session(user, request):
    """Creates a UserSession synchronously — session creation happens once per
    login, not per request, so it doesn't need to go through Celery."""
    from .models import UserSession

    user_agent = request.META.get("HTTP_USER_AGENT", "")
    return UserSession.objects.create(
        user=user,
        session_key=str(uuid.uuid4()),
        ip_address=_get_ip(request),
        user_agent=user_agent[:255],
        device_type=_detect_device_type(user_agent),
    )


def end_session(session_key: str) -> None:
    """Dispatches end_session_task — returns immediately, never blocks the
    logout response."""
    from .tasks import end_session_task

    end_session_task.delay(session_key)


def end_all_user_sessions(user) -> None:
    """Terminate all active sessions for a user and clear the cached session key."""
    from django.core.cache import cache
    from django.utils import timezone
    from .models import UserSession

    UserSession.objects.filter(user=user, is_active=True).update(
        is_active=False, ended_at=timezone.now()
    )
    cache.delete(f"activity:session:{user.pk}")


def _build_activity_payload(user, session, request, response, duration_ms, request_id):
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    return {
        "user_id": user.id if getattr(user, "id", None) else None,
        "session_id": session.id if session is not None else None,
        "request_id": request_id,
        "service": resolve_service(request.path),
        "action": resolve_action(method=request.method, path=request.path),
        "path": request.path[:500],
        "method": request.method,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "ip_address": _get_ip(request),
        "device_type": _detect_device_type(user_agent),
        "referrer": request.META.get("HTTP_REFERER", "")[:500],
    }


def record_activity(request, response, session, duration_ms, request_id=None) -> None:
    """
    Builds the UserActivity payload and dispatches it to the "activity"
    Celery queue. Wrapped so a dispatch failure is logged but never raises —
    analytics must never break the HTTP response.
    """
    from .tasks import record_activity_task

    try:
        user = getattr(request, "user", None)
        payload = _build_activity_payload(user, session, request, response, duration_ms, request_id)
        record_activity_task.apply_async(kwargs={"payload": payload}, queue="activity")
    except Exception as exc:
        logger.warning(
            "record_activity: dispatch failed: %s", exc,
            extra={"event_name": "activity.record.dispatch_failed"},
        )
