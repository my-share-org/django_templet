import logging

from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in, user_logged_out

logger = logging.getLogger("django.logs.app")


class ActivityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.activity'
    verbose_name = 'Activity Tracking'

    def ready(self):
        user_logged_in.connect(_on_user_logged_in)
        user_logged_out.connect(_on_user_logged_out)


def _on_user_logged_in(sender, request, user, **kwargs):
    if request is None:
        return
    try:
        from django.core.cache import cache
        from .models import UserSession
        from .services import start_session

        cache_key = f"activity:session:{user.pk}"
        session = (
            UserSession.objects.filter(user=user, is_active=True)
            .order_by("-started_at")
            .first()
        )
        if session is None:
            session = start_session(user, request)
        cache.set(cache_key, session.session_key, timeout=3600)
    except Exception as exc:
        logger.warning(
            "activity.apps: login signal handler failed: %s", exc,
            extra={"event_name": "activity.signal.login_error"},
        )


def _on_user_logged_out(sender, request, user, **kwargs):
    if user is None or request is None:
        return
    try:
        from django.core.cache import cache
        from .models import UserSession
        from .services import end_session

        cache_key = f"activity:session:{user.pk}"
        session_key = cache.get(cache_key)
        if not session_key:
            session = (
                UserSession.objects.filter(user=user, is_active=True)
                .order_by("-started_at")
                .first()
            )
            session_key = session.session_key if session else None
        if session_key:
            end_session(session_key)
        cache.delete(cache_key)
    except Exception as exc:
        logger.warning(
            "activity.apps: logout signal handler failed: %s", exc,
            extra={"event_name": "activity.signal.logout_error"},
        )
