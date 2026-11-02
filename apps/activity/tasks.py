import logging

from celery import shared_task
from django.db import IntegrityError, OperationalError

logger = logging.getLogger("django.logs.app")


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    queue="activity",
)
def record_activity_task(self, payload: dict) -> None:
    from .models import UserActivity

    try:
        UserActivity.objects.create(**payload)
    except IntegrityError as exc:
        # FK violation — not transient; do not retry.
        logger.warning(
            "record_activity_task: IntegrityError — row dropped: %s", exc,
            extra={"event_name": "activity.record.integrity_error"},
        )


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    queue="activity",
)
def end_session_task(self, session_key: str) -> None:
    from django.utils import timezone
    from .models import UserSession

    try:
        session = UserSession.objects.get(session_key=session_key)
    except UserSession.DoesNotExist:
        logger.warning(
            "end_session_task: session not found — key=%s", session_key,
            extra={"event_name": "activity.session.not_found"},
        )
        return

    session.ended_at = timezone.now()
    session.is_active = False
    session.save(update_fields=["ended_at", "is_active", "updated_at"])
