from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.throttles import (
    LoginThrottle,
    LoginTargetThrottle,
    ResetPasswordThrottle,
    ResetPasswordTargetThrottle,
)
from apps.authentication.v1.views import LoginView, ResetPasswordView

User = get_user_model()


class AuthenticationThrottleConfigTests(APITestCase):
    def test_login_view_has_dual_throttles(self):
        throttle_classes = LoginView.throttle_classes
        self.assertIn(LoginThrottle, throttle_classes)
        self.assertIn(LoginTargetThrottle, throttle_classes)

    def test_reset_password_view_has_dual_throttles(self):
        throttle_classes = ResetPasswordView.throttle_classes
        self.assertIn(ResetPasswordThrottle, throttle_classes)
        self.assertIn(ResetPasswordTargetThrottle, throttle_classes)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class LoginTargetThrottleTests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(email="target@example.com", password="SecurePassword123!")

    def test_login_target_throttle_blocks_brute_force_across_rotating_ips(self):
        with patch.object(LoginTargetThrottle, "get_rate", return_value="2/min"):
            # Attempt 1 from IP 1
            r1 = self.client.post(
                "/v1/auth/login/",
                {"email": "target@example.com", "password": "WrongPassword1"},
                REMOTE_ADDR="198.51.100.1",
                format="json",
            )
            self.assertEqual(r1.status_code, status.HTTP_401_UNAUTHORIZED)

            # Attempt 2 from IP 2 (attacker rotates IP)
            r2 = self.client.post(
                "/v1/auth/login/",
                {"email": "target@example.com", "password": "WrongPassword2"},
                REMOTE_ADDR="198.51.100.2",
                format="json",
            )
            self.assertEqual(r2.status_code, status.HTTP_401_UNAUTHORIZED)

            # Attempt 3 from IP 3 -> target rate limit exceeded (429) regardless of new IP!
            r3 = self.client.post(
                "/v1/auth/login/",
                {"email": "target@example.com", "password": "WrongPassword3"},
                REMOTE_ADDR="198.51.100.3",
                format="json",
            )
            self.assertEqual(r3.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
