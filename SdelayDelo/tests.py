from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.utils.timezone import now
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model


from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from freezegun import freeze_time

from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from datetime import timedelta
import tempfile
import os

from tasks.models import Tag


media_root = settings.MEDIA_ROOT
User = get_user_model()


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
        return self.client.get(self.test_url, HTTP_X_STATUS=status_code)

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
        self.assertIn("Ur ip has been baned", response.content.decode())

    @freeze_time("2025-01-01 12:00:00")
    @override_settings(
        ERROR_THRESHOLD=3, ERROR_WINDOW_MINUTES=1, BAN_DURATION_MINUTES=5
    )
    def test_ip_unbanned_after_timeout(self):
        """
        Test that an IP address is unbanned after the ban duration expires.

        Steps:
        1. Simulate `ERROR_THRESHOLD` number of error responses to trigger a ban.
        2. Confirm the IP is banned immediately after reaching the threshold.
        3. Advance time beyond the ban duration and verify the IP is unbanned.
        """
        # Trigger the ban
        for _ in range(settings.ERROR_THRESHOLD):
            self.simulate_request(400)

        # Confirm the IP is banned
        response = self.simulate_request(400)
        self.assertEqual(response.status_code, 403)

        # Move time forward to after the ban duration
        unban_time = now() + timedelta(minutes=settings.BAN_DURATION_MINUTES + 1)
        with freeze_time(unban_time):
            response = self.simulate_request(200)
            self.assertNotEqual(response.status_code, 403)  # Ban lifted


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(), MEDIA_URL="/media/", DEBUG=False, ALLOWED_HOSTS=["*"]
)
class SecureMediaTests(StaticLiveServerTestCase):
    """
    Comprehensive test suite for secure media serving functionality.
    Validates authorization, ownership checks, and error handling.
    """

    @classmethod
    def setUpClass(cls):
        """Initialize test environment with headless Chrome and test assets"""
        super().setUpClass()

        # Configure headless Chrome
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        cls.selenium = Chrome(
            service=Service(ChromeDriverManager().install()), options=chrome_options
        )

        # Create test media directory
        media_root = settings.MEDIA_ROOT
        icons_dir = os.path.join(media_root, "icons")
        os.makedirs(icons_dir, exist_ok=True)

        # Generate test PNG file
        test_png = os.path.join(icons_dir, "test.png")
        with open(test_png, "wb") as f:
            f.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

    @classmethod
    def tearDownClass(cls):
        """Cleanup test environment"""
        cls.selenium.quit()
        super().tearDownClass()

    def _get_http_status(self):
        """Retrieve HTTP status code using browser performance API"""
        return self.selenium.execute_script(
            "return window.performance.getEntries()[0].responseStatus;"
        )

    def _set_auth_header(self, token):
        """Set Authorization header using Chrome DevTools Protocol"""
        self.selenium.execute_cdp_cmd("Network.enable", {})
        headers = {"Authorization": f"Token {token}"} if token else {}
        self.selenium.execute_cdp_cmd(
            "Network.setExtraHTTPHeaders", {"headers": headers}
        )

    def test_authorized_access(self):
        """
        Verify successful media access for resource owner:
        - Authenticated user
        - Valid ownership
        - Existing media file
        """
        # Create test user and associated resources
        user = User.objects.create_user("testuser", password="testpass123")
        token = Token.objects.create(user=user)
        Tag.objects.create(
            user=user, title="Test Tag", colour="#FF0000", icon="icons/test.png"
        )

        # Configure headers and make request
        self._set_auth_header(token.key)
        self.selenium.get(f"{self.live_server_url}/media/icons/test.png")

        # Verify successful response
        self.assertEqual(self._get_http_status(), 200)
        self.assertTrue(self.selenium.find_element(By.TAG_NAME, "img").is_displayed())

    def test_unauthorized_access(self):
        """
        Validate access restrictions for:
        - Unauthenticated requests
        - Invalid credentials
        - Non-owner access
        """
        # Setup test data
        owner = User.objects.create_user("owner", password="ownerpass")
        other_user = User.objects.create_user("other", password="otherpass")
        Token.objects.create(user=owner)
        other_token = Token.objects.create(user=other_user)
        Tag.objects.create(
            user=owner,
            title="Protected Tag",
            colour="#00FF00",
            icon="icons/test.png",
        )

        # Case 1: No authentication
        self.selenium.get(f"{self.live_server_url}/media/icons/test.png")
        self.assertEqual(self._get_http_status(), 403)

        # Case 2: Invalid token
        self._set_auth_header("invalid-token-123")
        self.selenium.get(f"{self.live_server_url}/media/icons/test.png")
        self.assertEqual(self._get_http_status(), 403)

        # Case 3: Valid token for non-owner
        self._set_auth_header(other_token.key)
        self.selenium.get(f"{self.live_server_url}/media/icons/test.png")
        self.assertEqual(self._get_http_status(), 403)

    def test_file_validation(self):
        """
        Verify proper handling of:
        - Non-existent files (404)
        - Orphaned files (404)
        - Malformed requests (400)
        """
        # Test non-existent file
        self.selenium.get(f"{self.live_server_url}/media/icons/nonexistent.file")
        self.assertEqual(self._get_http_status(), 404)

        # Create orphaned file (no database record)
        orphan_path = os.path.join(settings.MEDIA_ROOT, "icons/orphan.png")
        with open(orphan_path, "wb") as f:
            f.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        self.selenium.get(f"{self.live_server_url}/media/icons/orphan.png")
        self.assertEqual(self._get_http_status(), 200)
