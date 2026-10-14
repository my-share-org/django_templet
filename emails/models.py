from django.db import models

from core.models import BaseModel
from emails.choices import EmailBodyType, EmailStatus, EmailPurpose


class EmailLog(BaseModel):
    to_emails  = models.TextField()
    bcc        = models.TextField(blank=True, null=True)
    from_email = models.EmailField()

    subject   = models.CharField(max_length=255, blank=True, null=True)
    body      = models.TextField(blank=True, null=True)
    body_type = models.CharField(max_length=255, choices=EmailBodyType.choices, default=EmailBodyType.TEXT)
    purpose   = models.CharField(max_length=50, choices=EmailPurpose.choices, default=EmailPurpose.OTHERS, db_index=True)

    status    = models.CharField(max_length=255, choices=EmailStatus.choices, default=EmailStatus.PENDING)
    try_count = models.IntegerField(default=1)

    schedule_at = models.DateTimeField(blank=True, null=True)
    sent_at     = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'
        indexes = [
            models.Index(fields=["status", "-created_at"], name="emaillog_status_created_idx"),
            models.Index(fields=["-created_at"], name="emaillog_created_idx"),
        ]

    def __str__(self):
        return f"{self.subject} → {self.to_emails} [{self.status}]"
