from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.utils.timezone import now

from rest_framework.test import APIClient

from datetime import timedelta

from freezegun import freeze_time


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
