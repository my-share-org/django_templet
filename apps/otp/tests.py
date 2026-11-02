from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.otp.choices import OtpChannel, OtpPurpose
from apps.otp.services.rules import get_otp_rules

User = get_user_model()

GET_OTP_URL = "/v1/otp/get-otp/"


class OtpPolicyTableTests(APITestCase):
    def test_policy_field_order_matches_table_header(self):
        reg = get_otp_rules(OtpPurpose.REGISTRATION)
        self.assertEqual(
            (reg.enable, reg.require_auth, reg.require_identifier,
             reg.check_user_exists, reg.allow_duplicate),
            (True, False, True, False, False),
        )
        ce = get_otp_rules(OtpPurpose.CHANGE_EMAIL)
        self.assertEqual(
            (ce.enable, ce.require_auth, ce.require_identifier,
             ce.check_user_exists, ce.allow_duplicate),
            (True, True, False, True, True),
        )

    def test_lookup_works_with_raw_string_purpose(self):
        self.assertIs(get_otp_rules("password_reset"), get_otp_rules(OtpPurpose.PASSWORD_RESET))

    def test_unknown_purpose_raises(self):
        with self.assertRaises(ValueError):
            get_otp_rules("nonsense")


# Local cache so throttling never needs a live Redis during tests
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
@patch("apps.otp.v1.views.OTPService.send")
class GetOtpRouteTests(APITestCase):
    def setUp(self):
        # Throttle history is keyed by IP and would leak across tests
        from django.core.cache import cache
        cache.clear()

    def post(self, body):
        return self.client.post(GET_OTP_URL, body, format="json")

    def assert_error(self, response, status_code, message_part, send_mock):
        self.assertEqual(response.status_code, status_code, response.data)
        self.assertFalse(response.data["success"])
        self.assertIn(message_part.lower(), response.data["message"].lower())
        send_mock.assert_not_called()

    def test_missing_purpose(self, send_mock):
        self.assert_error(self.post({}), 400, "Missing required field(s): purpose", send_mock)

    def test_wrong_type_purpose(self, send_mock):
        self.assert_error(self.post({"purpose": 5}), 400, "must be of type str", send_mock)

    def test_invalid_purpose(self, send_mock):
        self.assert_error(self.post({"purpose": "hack"}), 400, "valid value", send_mock)

    def test_disabled_purpose(self, send_mock):
        self.assert_error(
            self.post({"purpose": "login", "user_identifier": "a@b.com"}),
            400, "not enabled", send_mock,
        )

    def test_auth_required_purpose_anonymous(self, send_mock):
        self.assert_error(self.post({"purpose": "change_email"}), 401, "Authentication required", send_mock)

    def test_registration_missing_identifier(self, send_mock):
        self.assert_error(self.post({"purpose": "registration"}), 400, "user_identifier", send_mock)

    def test_registration_invalid_email(self, send_mock):
        self.assert_error(
            self.post({"purpose": "registration", "user_identifier": "not-an-email"}),
            400, "Invalid user identifier", send_mock,
        )

    def test_registration_fresh_email_sends_otp(self, send_mock):
        response = self.post({"purpose": "registration", "user_identifier": "new@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["success"])
        send_mock.assert_called_once_with(
            user="new@example.com",
            purpose=OtpPurpose.REGISTRATION,
            channel=OtpChannel.EMAIL,
        )

    def test_registration_duplicate_email_rejected(self, send_mock):
        User.objects.create_user(email="taken@example.com", password="Str0ng-Pass!42")
        self.assert_error(
            self.post({"purpose": "registration", "user_identifier": "taken@example.com"}),
            400, "already exists", send_mock,
        )

    def test_password_reset_requires_existing_user(self, send_mock):
        # 1. Non-existent user should fail with 404
        self.assert_error(
            self.post({"purpose": "password_reset", "user_identifier": "nonexistent@example.com"}),
            404, "User not found", send_mock,
        )

        # 2. Existing user succeeds
        User.objects.create_user(email="registered@example.com", password="Str0ng-Pass!42")
        response = self.post({"purpose": "password_reset", "user_identifier": "registered@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        send_mock.assert_called_once()

    def test_target_identifier_throttle_blocks_rotating_ips(self, send_mock):
        from apps.otp.throttles import OtpTargetRateThrottle
        with patch.object(OtpTargetRateThrottle, "get_rate", return_value="2/hour"):
            # Request 1 from IP 1
            r1 = self.client.post(
                GET_OTP_URL,
                {"purpose": "registration", "user_identifier": "victim@example.com"},
                REMOTE_ADDR="198.51.100.1",
                format="json",
            )
            self.assertEqual(r1.status_code, status.HTTP_200_OK)

            # Request 2 from IP 2 (attacker rotates IP)
            r2 = self.client.post(
                GET_OTP_URL,
                {"purpose": "registration", "user_identifier": "victim@example.com"},
                REMOTE_ADDR="198.51.100.2",
                format="json",
            )
            self.assertEqual(r2.status_code, status.HTTP_200_OK)

            # Request 3 from IP 3 -> target rate limit exceeded (429) even though IP is brand new!
            r3 = self.client.post(
                GET_OTP_URL,
                {"purpose": "registration", "user_identifier": "victim@example.com"},
                REMOTE_ADDR="198.51.100.3",
                format="json",
            )
            self.assertEqual(r3.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
