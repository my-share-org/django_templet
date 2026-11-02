import smtplib
from django.conf import settings
from django.core.cache import cache
from apps.core.utils.health_response import health_ok_response, health_error_response

_CACHE_KEY = "health:email_service"
_CACHE_TTL = 60  # seconds


def check_email_service():
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    result = _run_smtp_check()
    cache.set(_CACHE_KEY, result, _CACHE_TTL)
    return result


def _run_smtp_check():
    try:
        if settings.EMAIL_PORT == 465:
            server = smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=5)
        else:
            server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=5)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)

        code, message = server.noop()
        if code != 250:
            raise smtplib.SMTPException(f"SMTP NOOP failed: {message.decode()}")

        server.quit()
        return health_ok_response(name="Email Service")

    except smtplib.SMTPAuthenticationError as e:
        return health_error_response(
            name="Email Service",
            message="SMTP authentication failed",
            errors=e,
        )
    except smtplib.SMTPException as e:
        return health_error_response(
            name="Email Service",
            message="SMTP server error",
            errors=e,
        )
    except Exception as e:
        return health_error_response(
            name="Email Service",
            message="Email service check failed",
            errors=e,
        )
