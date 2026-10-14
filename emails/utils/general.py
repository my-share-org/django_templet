from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from emails.models import EmailLog
from emails.choices import (
    EmailStatus,
    EmailBodyType,
    EmailPurpose,
)
from emails.serializers import EmailLogSerializer


def send_email_core(
    *,
    subject: str,
    to_emails: list[str],
    bcc: list[str] = None,
    from_email: str = settings.DEFAULT_FROM_EMAIL,
    body: str = "",
    log_body: str = None,
    body_type: EmailBodyType = EmailBodyType.HTML,
    email_log_id: int = None,
    purpose: EmailPurpose = EmailPurpose.OTHERS,
):
    """
    Send email core function.

    Parameters:
        from_email (str): From email address.
        to_emails (list[str]): To email address.
        subject (str): Email subject.
        body (str): Email body sent to recipient.
        log_body (str, optional): Masked/sanitized body saved to EmailLog.
        body_type (EmailBodyType): Email body type.
        email_log_id (int): Email log id.
        purpose (EmailPurpose): Email purpose.
    """
    email_log = None

    if email_log_id:
        try:
            email_log = EmailLog.objects.get(id=email_log_id)
            email_log.try_count += 1
            email_log.save(update_fields=["try_count"])
        except EmailLog.DoesNotExist:
            pass

    if not email_log:
        saved_body = log_body or body

        log_serializer = EmailLogSerializer(
            data={
                "from_email": from_email,
                "to_emails": ",".join(to_emails),
                "bcc": ",".join(bcc) if bcc else None,
                "subject": subject,
                "body": saved_body,
                "body_type": body_type,
                "purpose": purpose,
                "status": EmailStatus.PENDING,
            }
        )
        log_serializer.is_valid(raise_exception=True)
        email_log = log_serializer.save()

    def _send():
        email = EmailMultiAlternatives(
            subject=subject,
            body=body if body_type == EmailBodyType.TEXT else "",
            from_email=from_email,
            to=to_emails,
            bcc=bcc,
        )
        if body_type == EmailBodyType.HTML:
            email.attach_alternative(body, "text/html")

        try:
            email.send()
            EmailLog.objects.filter(id=email_log.id).update(
                status=EmailStatus.SENT,
                sent_at=timezone.now(),
            )
        except Exception as exc:
            EmailLog.objects.filter(id=email_log.id).update(
                status=EmailStatus.FAILED,
            )
            exc.email_log_id = email_log.id
            raise

    _send()
    return email_log

