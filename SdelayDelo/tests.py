from urllib import request
from django.test import TestCase, override_settings, RequestFactory, Client, tag
from django.urls import reverse
from django.conf import settings
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden, HttpResponse

from freezegun import freeze_time

from rest_framework.test import APIClient, APITestCase
from rest_framework.authtoken.models import Token

from datetime import timedelta
import tempfile
import os
import time
import logging
import redis
import sys
import unittest

from SdelayDelo.local_settings import ALLOWED_HOSTS
from tasks.models import Tag

from .middlewares import MediaServerMiddleware


logger = logging.getLogger(__name__)


media_root = settings.MEDIA_ROOT
User = get_user_model()


def reset_redis():
    """Complete Redis flush (use only for testing!)"""
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,  # Используйте ту же DB, что и в middleware
        )
        r.flushall()
    except redis.RedisError as e:
        print(f"[ERROR] Redis reset failed: {str(e)}")


class ErrorTrackingMiddlewareTest(TestCase):
    """
    Test suite for the ErrorTrackingMiddleware.

    Verifies:
    1. IP addresses are banned after exceeding the error threshold.
    2. Banned IPs are automatically unbanned after the ban duration expires.
    """

    def setUp(self):
        """
        Set up the test environment, including API client
        """
        reset_redis()
        self.client = APIClient()  # Initialize API client
        self.test_url = reverse("check_code")  # Test endpoint
        self.ip_address = "192.168.1.100"  # Test IP address

    def simulate_request(self, status_code):
        """
        Helper method to simulate a request with a specific status code.

        Args:
            status_code (int): The HTTP status code to simulate.

        Returns:
            Response: The simulated HTTP response.
        """
        self.client.defaults["REMOTE_ADDR"] = self.ip_address
        return self.client.post(self.test_url, HTTP_X_STATUS=status_code)

    @freeze_time("2025-01-01 12:00:00")
    @override_settings(
        ERROR_THRESHOLD=3, ERROR_WINDOW_MINUTES=1, BAN_DURATION_MINUTES=5
    )
    def test_ip_banned_after_threshold(self):
        """
        Test that an IP address is banned after exceeding the error threshold.

        Steps:
        1. Simulate `ERROR_THRESHOLD` number of error responses (status >= 400).
        2. Ensure the IP is not banned during the first `ERROR_THRESHOLD` requests.
        3. Verify the IP is banned on the next request with a 403 response.
        """
        for _ in range(settings.ERROR_THRESHOLD):
            response = self.simulate_request(400)
            self.assertNotEqual(response.status_code, 403)  # Not banned yet

        # The IP should now be banned
        response = self.simulate_request(400)
        self.assertEqual(response.status_code, 403)
        self.assertIn("IP blocked", response.content.decode())

    @freeze_time("2025-01-01 12:00:00")
    @unittest.skipUnless(
        "--tag=redis-unban-after-timeout" in sys.argv,
        "Long-running test (skipped by default)",
    )
    @tag("redis-unban-after-timeout")
    @override_settings(
        ERROR_THRESHOLD=3,
        ERROR_WINDOW_MINUTES=1,
        BAN_DURATION_MINUTES=1,
    )
    def test_ip_unbanned_after_timeout(self):
        for _ in range(settings.ERROR_THRESHOLD):
            self.simulate_request(400)

        response = self.simulate_request(400)
        self.assertEqual(response.status_code, 403)

        time.sleep(60)

        response = self.simulate_request(200)
        self.assertNotEqual(response.status_code, 403)


@override_settings(DEBUG=False, ALLOWED_HOSTS=["*"])
class Test404PageIsCustom(TestCase):
    """Tests if 404 is custom in debug=false mode"""

    def setUp(self):
        """Setting client for requesting"""
        self.client = Client(enforce_csrf_checks=False)

    def test_404(self):
        response = self.client.get("/this-url-definitely-does-not-exist/")

        self.assertEqual(response.status_code, 404)

        self.assertContains(
            response,
            "Запрошенная страница не существует.",
            status_code=404,
            html=True,
        )


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(), MEDIA_URL="/media/", DEBUG=False, ALLOWED_HOSTS=["*"]
)
class MediaAccessTests(TestCase):
    """Test suite for MediaServerMiddleware functionality.

    Test cases cover:
    - Successful authorized access to protected media
    - Various unauthorized access scenarios
    - Proper handling of non-existing files
    - Whitelisting of non-media paths
    """

    def setUp(self):
        """Initialize test environment with users and test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.token = Token.objects.create(user=self.user)
        self.other_user = User.objects.create_user(
            username="other", password="otherpass"
        )

        # Create test media object
        self.tag = Tag.objects.create(
            user=self.user, title="Test Tag", colour="#FF0000", icon="icons/test.png"
        )

        media_root = settings.MEDIA_ROOT
        icons_dir = os.path.join(media_root, "icons")
        os.makedirs(icons_dir, exist_ok=True)

        test_png = os.path.join(icons_dir, "test.png")
        with open(test_png, "wb") as f:
            f.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

    def test_authorized_access(self):
        """Verify successful access with valid credentials."""
        request = self.factory.get(
            "/media/icons/test.png", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )
        response = MediaServerMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_no_credentials(self):
        """Test access denial without authentication."""
        request = self.factory.get("/media/icons/test.png")
        response = MediaServerMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(response.status_code, 403)

    def test_unauthorized_invalid_token(self):
        """Test access denial with invalid token."""
        request = self.factory.get(
            "/media/icons/test.png", HTTP_AUTHORIZATION="Token invalid-token-123"
        )
        response = MediaServerMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(response.status_code, 403)

    def test_unauthorized_wrong_user(self):
        """Test access denial with valid token for non-owner."""
        other_token = Token.objects.create(user=self.other_user)
        request = self.factory.get(
            "/media/icons/test.png", HTTP_AUTHORIZATION=f"Token {other_token.key}"
        )
        response = MediaServerMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(response.status_code, 403)

    def test_non_existing_file(self):
        """Verify proper handling of non-existent files."""
        request = self.factory.get("/media/icons/non_existent.jpg")
        response = MediaServerMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(response.status_code, 404)

    def test_non_media_access(self):
        """Verify whitelisting of non-media paths."""
        request = self.factory.get("/some/other/path")
        response = MediaServerMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(response.status_code, 200)


class EmailLocalSettingsTest(APITestCase):
    """Tests if EMAIL_EXISTS param changes views behavior."""

    @override_settings(EMAIL_EXISTS=True)
    def test_email_exists(self):
        """Test if the view returns 200 when email exists."""
        response = self.client.post(reverse("send_code"), {"email": "test@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "Server need an email configuration. Check local settings",
            str(response.data),
        )

        response = self.client.post(reverse("check_code"), {"code": "123456"})
        self.assertNotIn(
            "Server need an email configuration. Check local settings",
            str(response.data),
        )

        response = self.client.post(
            reverse("reset_password"), {"email": "test@example.com"}
        )
        self.assertNotIn(
            "Server need an email configuration. Check local settings",
            str(response.data),
        )

    @override_settings(EMAIL_EXISTS=False)
    def test_email_not_exists(self):
        """Test if the view returns 400 and message when email doesn't exists."""
        response = self.client.post(reverse("send_code"), {"email": "test@example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Server need an email configuration. Check local settings",
            str(response.data),
        )

        response = self.client.post(reverse("check_code"), {"code": "123456"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Server need an email configuration. Check local settings",
            str(response.data),
        )

        response = self.client.post(
            reverse("reset_password"), {"email": "test@example.com"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Server need an email configuration. Check local settings",
            str(response.data),
        )
