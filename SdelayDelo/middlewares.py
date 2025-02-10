from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now
from django.http import HttpResponse
from django.contrib.auth.models import AnonymousUser

from rest_framework.authtoken.models import Token

from tasks.models import Tag

import os
import logging

logger = logging.getLogger(__name__)


class MediaServerMiddleware:
    """Middleware to secure all icons from other"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """If media file and blocks if u are not author of media. Not blocks if there is no author"""

        self.request = request

        token_key = self.get_token_key(request)
        self.user = AnonymousUser
        if token_key:
            try:
                token = Token.objects.get(key=token_key)
                self.user = token.user
            except Token.DoesNotExist:
                logger.debug("Token not found in database.")
            except Exception as e:
                logger.error(
                    f"Unexpected error during token authentication: {e}", exc_info=True
                )
        else:
            logger.debug("No token key found in request.")

        response = self.get_response(request)
        logger.debug(f"Get {request.path} from {self.user}")
        if request.path.startswith("/media/"):
            path_to_media = request.path.replace("/media/", "")
            if not os.path.exists(f"{settings.MEDIA_ROOT}/{path_to_media}"):
                return HttpResponse("File is not existed", status=404)
            tags = Tag.objects.filter(icon=path_to_media)
            if not tags.filter(user=self.user.pk).exists() and tags.exists():
                return HttpResponse("Access denied", status=403)

        return response

    def get_token_key(self, request):
        """
        Extracts the token key from the request headers.
        You might need to adjust this depending on how your client sends the token.
        """
        auth_header = request.META.get(
            "HTTP_AUTHORIZATION", ""
        )  # Get the Authorization header
        if auth_header.startswith("Token "):
            return auth_header[6:]  # Remove "Token " prefix
        return None


class ErrorTrackingMiddleware:
    """Bans if too many errors"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_logs = {}
        self.banned_ips = {}
        self.error_threshold = getattr(settings, "ERROR_THRESHOLD", 10)
        self.ban_duration_hours = getattr(settings, "BAN_DURATION_MINUTES", 60) / 60
        self.error_window_minutes = getattr(settings, "ERROR_WINDOW_MINUTES", 10)

    def __call__(self, request):
        ip_address = self.get_client_ip(request)
        current_time = now()

        # Unban IP if the ban duration has expired
        if ip_address in self.banned_ips:
            ban_end_time = self.banned_ips[ip_address]
            if current_time > ban_end_time:
                del self.banned_ips[ip_address]
            else:
                return HttpResponse(
                    "Ur ip has been baned due too many mistakes. Try again later",
                    status=403,
                )

        # Process the request and log errors if necessary
        response = self.get_response(request)
        if response.status_code >= 400 and response.status_code != 404:
            self.log_error(ip_address, current_time)
        return response

    def log_error(self, ip_address, current_time):
        window_start = current_time - timedelta(minutes=self.error_window_minutes)
        if ip_address not in self.error_logs:
            self.error_logs[ip_address] = []
        self.error_logs[ip_address] = [
            ts for ts in self.error_logs[ip_address] if ts > window_start
        ]
        self.error_logs[ip_address].append(current_time)
        if len(self.error_logs[ip_address]) >= self.error_threshold:
            self.banned_ips[ip_address] = current_time + timedelta(
                hours=self.ban_duration_hours
            )

    @staticmethod
    def get_client_ip(request):
        return request.META.get("REMOTE_ADDR", "")
