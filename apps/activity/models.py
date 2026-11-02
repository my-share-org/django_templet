from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from .choices import ActivityAction


class UserSession(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    session_key = models.CharField(max_length=100, unique=True, db_index=True)
    started_at  = models.DateTimeField(auto_now_add=True)
    ended_at    = models.DateTimeField(null=True, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "activity_user_session"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "started_at"]),
            models.Index(fields=["started_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.session_key[:8]}…"

    @property
    def duration_seconds(self) -> int | None:
        if self.ended_at is None:
            return None
        return int((self.ended_at - self.started_at).total_seconds())


class UserActivity(BaseModel):
    """
    One row per tracked HTTP request. Owns every field describing the request
    directly — no FK to a shared "request context" table. `request_id` is a
    soft correlation key to logs.SystemLog.request_id (same pattern, never a
    FK) so the two independent systems can be joined at query time only.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="activities",
    )
    session = models.ForeignKey(
        UserSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    request_id  = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    service     = models.CharField(max_length=50, db_index=True)
    action      = models.CharField(max_length=50, choices=ActivityAction.choices, db_index=True)
    path        = models.CharField(max_length=500)
    method      = models.CharField(max_length=10)
    status_code = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    referrer    = models.CharField(max_length=500, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_user_activity"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["user", "service", "occurred_at"]),
            models.Index(fields=["service", "action"]),
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["user", "action", "occurred_at"]),
            models.Index(fields=["status_code", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.service}:{self.action} [{self.status_code}]"
