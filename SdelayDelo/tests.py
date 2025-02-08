from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.utils.timezone import now
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


from rest_framework.test import APIClient

from datetime import timedelta
import tempfile
import os

from freezegun import freeze_time


media_root = settings.MEDIA_ROOT


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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), MEDIA_URL="/media/")
class MediaFileTests(StaticLiveServerTestCase):
    """
    Test class for verifying media file serving functionality.

    Attributes:
        selenium (WebDriver): Instance of Chrome WebDriver
        media_root (str): Path to temporary media directory
    """

    @classmethod
    def setUpClass(cls):
        """
        Class-level setup method:
        - Initializes Chrome WebDriver with automatic driver management
        - Creates temporary media directory structure
        - Generates test PNG file
        """
        super().setUpClass()

        # Configure Chrome WebDriver with automatic driver installation
        service = Service(ChromeDriverManager().install())
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        cls.selenium = Chrome(service=service, options=options)

        # Create test media directory and sample file
        cls.media_root = settings.MEDIA_ROOT  # Fixed: Access via django.conf.settings
        icons_dir = os.path.join(cls.media_root, "icons")
        os.makedirs(icons_dir, exist_ok=True)

        # Create minimal valid PNG file
        test_png_path = os.path.join(icons_dir, "test.png")
        with open(test_png_path, "wb") as f:
            f.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

    @classmethod
    def tearDownClass(cls):
        """
        Class-level teardown method:
        - Quits WebDriver instance
        - Cleans up parent class resources
        """
        cls.selenium.quit()
        super().tearDownClass()

    def test_existing_media_file(self):
        """
        Verify successful serving of existing media file:
        - Access test PNG file via URL
        - Check correct Content-Type header
        """
        url = f"{self.live_server_url}/media/icons/test.png"
        self.selenium.get(url)

        # Verify correct content type using JavaScript execution
        content_type = self.selenium.execute_script("return document.contentType")
        self.assertEqual(content_type, "image/png")

    def test_non_existing_media_file(self):
        """
        Verify proper error handling for non-existent files:
        - Access invalid media URL
        - Check 404 status code
        - Verify error message presence
        """
        url = f"{self.live_server_url}/media/non-existed-file"
        self.selenium.get(url)

        # Get performance entry for status code verification
        performance = self.selenium.execute_script(
            "return window.performance.getEntries()[0]"
        )
        self.assertEqual(performance["responseStatus"], 404)

        # Check for error message in page content
        self.assertIn("Not Found", self.selenium.page_source)
