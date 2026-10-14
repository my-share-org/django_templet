from unittest.mock import patch
from django.test import TestCase

from emails.choices import EmailPurpose
from emails.models import EmailLog
from emails.utils.general import send_email_core
from emails.services.otp import send_otp_email


class EmailMaskingTests(TestCase):
    def test_send_email_core_with_log_body_stores_masked_content(self):
        send_email_core(
            subject="Your OTP",
            to_emails=["user@example.com"],
            body="<html>Your OTP is 123456</html>",
            log_body="<html>Your OTP is ******</html>",
            purpose=EmailPurpose.OTP,
        )

        log = EmailLog.objects.filter(to_emails="user@example.com").first()
        self.assertIsNotNone(log)
        self.assertIn("******", log.body)
        self.assertNotIn("123456", log.body)
        self.assertEqual(log.purpose, EmailPurpose.OTP)

    def test_send_email_core_without_log_body_stores_original_body(self):
        send_email_core(
            subject="Welcome!",
            to_emails=["newuser@example.com"],
            body="<html>Welcome to the platform!</html>",
            purpose=EmailPurpose.WELCOME,
        )

        log = EmailLog.objects.filter(to_emails="newuser@example.com").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.body, "<html>Welcome to the platform!</html>")
        self.assertEqual(log.purpose, EmailPurpose.WELCOME)

    @patch("emails.services.otp.send_email_task.delay")
    def test_send_otp_email_passes_masked_log_body(self, mock_delay):
        send_otp_email(email="test@example.com", otp="987654")

        mock_delay.assert_called_once()
        kwargs = mock_delay.call_args.kwargs
        self.assertIn("987654", kwargs["body"])
        self.assertIn("******", kwargs["log_body"])
        self.assertNotIn("987654", kwargs["log_body"])

    def test_send_email_core_marks_sent_and_records_sent_at(self):
        from emails.choices import EmailStatus
        log = send_email_core(
            subject="Success test",
            to_emails=["success@example.com"],
            body="Hello",
            purpose=EmailPurpose.OTHERS,
        )
        log.refresh_from_db()
        self.assertEqual(log.status, EmailStatus.SENT)
        self.assertIsNotNone(log.sent_at)

    @patch("django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("SMTP down"))
    def test_send_email_core_marks_failed_on_send_error(self, mock_send):
        from emails.choices import EmailStatus
        with self.assertRaises(Exception):
            send_email_core(
                subject="Fail test",
                to_emails=["fail@example.com"],
                body="Hello",
                purpose=EmailPurpose.OTHERS,
            )
        log = EmailLog.objects.filter(to_emails="fail@example.com").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, EmailStatus.FAILED)

    def test_send_email_core_reuses_existing_log_and_increments_try_count(self):
        log1 = send_email_core(
            subject="Retry test",
            to_emails=["retry@example.com"],
            body="First try",
            purpose=EmailPurpose.OTHERS,
        )
        self.assertEqual(log1.try_count, 1)

        log2 = send_email_core(
            subject="Retry test",
            to_emails=["retry@example.com"],
            body="Second try",
            email_log_id=log1.id,
            purpose=EmailPurpose.OTHERS,
        )
        log1.refresh_from_db()
        self.assertEqual(log1.id, log2.id)
        self.assertEqual(log1.try_count, 2)
        self.assertEqual(EmailLog.objects.filter(to_emails="retry@example.com").count(), 1)
