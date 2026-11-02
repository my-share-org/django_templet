from apps.otp.choices import OtpPurpose
from django.template.loader import render_to_string
from apps.emails.tasks import send_email_task
from apps.emails.choices import EmailBodyType, EmailPurpose


def send_otp_email(email: str, otp: str, otp_purpose: str = OtpPurpose.OTHER):
    rendered_body = render_to_string(
        "otp_body.html",
        {
            "otp": otp,
            "purpose": otp_purpose,
        },
    )
    masked_body = render_to_string(
        "otp_body.html",
        {
            "otp": "******",
            "purpose": otp_purpose,
        },
    )
    send_email_task.delay(
        subject=f"Your OTP Code",
        to_emails=[email],
        body=rendered_body,
        log_body=masked_body,
        body_type=EmailBodyType.HTML,
        purpose=EmailPurpose.OTP,
    )
