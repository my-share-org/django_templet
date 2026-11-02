from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from apps.core.throttles import AuthenticatedUserRateThrottle, TargetIdentifierRateThrottle
from apps.core.views import HealthCheckView

User = get_user_model()


class HealthCheckThrottleTests(APITestCase):
    def test_health_check_exempt_from_throttling(self):
        client = APIClient()
        for _ in range(25):
            response = client.get("/health/")
            self.assertEqual(response.status_code, 200)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class CoreThrottlesUnitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.factory = RequestFactory()

    def test_authenticated_user_throttle_bypasses_anonymous(self):
        throttle = AuthenticatedUserRateThrottle()
        request = self.factory.get("/")
        # Anonymous request -> user is AnonymousUser
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        cache_key = throttle.get_cache_key(request, None)
        self.assertIsNone(cache_key)

    def test_authenticated_user_throttle_keys_authenticated_user(self):
        throttle = AuthenticatedUserRateThrottle()
        user = User.objects.create_user(email="auth_user@example.com", password="Password123!")
        request = self.factory.get("/")
        request.user = user
        cache_key = throttle.get_cache_key(request, None)
        self.assertIsNotNone(cache_key)
        self.assertIn(str(user.pk), cache_key)

    def test_target_identifier_throttle_extracts_and_normalizes_data(self):
        throttle = TargetIdentifierRateThrottle()
        request = self.factory.post("/", {"email": "  Victim@Example.COM  "}, content_type="application/json")
        request.data = {"email": "  Victim@Example.COM  "}
        request.user = None
        cache_key = throttle.get_cache_key(request, None)
        self.assertIsNotNone(cache_key)
        self.assertIn("victim@example.com", cache_key)


class GetClientIpTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_direct_connection_uses_remote_addr(self):
        from apps.core.utils.general import get_client_ip
        request = self.factory.get("/", REMOTE_ADDR="198.51.100.22")
        self.assertEqual(get_client_ip(request), "198.51.100.22")

    def test_spoofed_x_forwarded_for_extracts_trusted_proxy_ip_from_right(self):
        from apps.core.utils.general import get_client_ip
        # Attacker injects fake IPs at the beginning: "1.1.1.1, 8.8.8.8".
        # Trusted reverse proxy appended actual client IP: "198.51.100.99".
        request = self.factory.get(
            "/",
            HTTP_X_FORWARDED_FOR="1.1.1.1, 8.8.8.8, 198.51.100.99",
            REMOTE_ADDR="10.0.0.1",
        )
        with self.settings(NUM_PROXIES=1):
            ip = get_client_ip(request)
            self.assertEqual(ip, "198.51.100.99")
            self.assertNotEqual(ip, "1.1.1.1")

    def test_multi_hop_proxy_chain_respects_num_proxies(self):
        from apps.core.utils.general import get_client_ip
        # Architecture: Client (198.51.100.5) -> CDN/LB -> Nginx -> Gunicorn
        # In a 2-proxy chain, the 2nd hop from the right is the genuine client:
        request = self.factory.get(
            "/",
            HTTP_X_FORWARDED_FOR="198.51.100.5, 172.16.0.2",
            REMOTE_ADDR="10.0.0.2",
        )
        with self.settings(NUM_PROXIES=2):
            self.assertEqual(get_client_ip(request), "198.51.100.5")

    def test_cloudflare_connecting_ip_takes_precedence(self):
        from apps.core.utils.general import get_client_ip
        request = self.factory.get(
            "/",
            HTTP_CF_CONNECTING_IP="203.0.113.88",
            HTTP_X_FORWARDED_FOR="1.1.1.1, 10.0.0.5",
            REMOTE_ADDR="10.0.0.1",
        )
        self.assertEqual(get_client_ip(request), "203.0.113.88")

    def test_malformed_ip_in_headers_safely_falls_back(self):
        from apps.core.utils.general import get_client_ip
        request = self.factory.get(
            "/",
            HTTP_X_FORWARDED_FOR="<script>alert(1)</script>, invalid-ip",
            REMOTE_ADDR="198.51.100.44",
        )
        self.assertEqual(get_client_ip(request), "198.51.100.44")
