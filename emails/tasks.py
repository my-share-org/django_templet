from celery import shared_task
from smtplib import SMTPException
from emails.utils.general import send_email_core

@shared_task(
    bind=True,
    max_retries=3,
)
def send_email_task(self, **kwargs):
    email_log_id = kwargs.get("email_log_id")
    try:
        log = send_email_core(**kwargs)
        return log.id if log else None
    except (SMTPException, ConnectionError) as exc:
        if not email_log_id and hasattr(exc, "email_log_id"):
            kwargs["email_log_id"] = exc.email_log_id
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown, kwargs=kwargs)