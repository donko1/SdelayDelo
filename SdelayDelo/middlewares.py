from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import AnonymousUser

from rest_framework.authtoken.models import Token

from tasks.models import Tag

import os
import logging

import redis

logger = logging.getLogger(__name__)


class MediaServerMiddleware:
    """Middleware to secure all icons from other"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """If media file and blocks if u are not author of media. Not blocks if there is no author"""

        self.request = request
        logger.info(f"Processing request for path: {request.path}")

        token_key = self.get_token_key(request)
        self.user = AnonymousUser
        if token_key:
            try:
                token = Token.objects.get(key=token_key)
                self.user = token.user
                logger.info(f"Authenticated user: {self.user}")
            except Token.DoesNotExist:
                logger.debug("Token not found in database.")
            except Exception as e:
                logger.error(
                    f"Unexpected error during token authentication: {e}", exc_info=True
                )
        else:
            logger.debug("No token key found in request.")

        response = self.get_response(request)
        if request.path.startswith("/media/"):
            try:
                logger.debug(f"Get {self.user} for {response.path}")
            except AttributeError:
                pass
            path_to_media = request.path.replace("/media/", "")
            if not os.path.exists(f"{settings.MEDIA_ROOT}/{path_to_media}"):
                logger.warning(f"File not found: {path_to_media}")
                return HttpResponse("File is not existed", status=404)
            tags = Tag.objects.filter(icon=path_to_media)
            if not tags.filter(user=self.user.pk).exists() and tags.exists():
                logger.warning(f"Access denied for user: {self.user}")
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
    """Middleware for tracking errors and banning IPs."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True,  # Auto-convert bytes to str
        )
        self.error_threshold = getattr(settings, "ERROR_THRESHOLD", 3)
        self.ban_duration = (
            getattr(settings, "BAN_DURATION_MINUTES", 60) * 60
        )  # in seconds
        self.error_window = (
            getattr(settings, "ERROR_WINDOW_MINUTES", 10) * 60
        )  # in seconds

    def __call__(self, request):
        ip = self._get_client_ip(request)

        # Check if IP is banned
        if self.redis.exists(f"banned:{ip}"):
            logger.info(f"IP {ip} is banned")
            return HttpResponse("IP blocked", status=403)

        response = self.get_response(request)

        # Log error for 400-499 status codes (except 404)
        if 400 <= response.status_code < 500 and response.status_code != 404:
            self._handle_error(ip)

        return response

    def _handle_error(self, ip):
        """Increment error counter and ban IP if threshold is reached."""
        error_key = f"errors:{ip}"
        banned_key = f"banned:{ip}"

        try:
            # Set initial counter with TTL if not exists, else increment
            error_count = self.redis.incr(error_key)
            if error_count == 1:  # Key was just created
                self.redis.expire(error_key, self.error_window)

            logger.debug(f"Error count for {ip}: {error_count}/{self.error_threshold}")

            # Ban IP if threshold reached
            if error_count >= self.error_threshold:
                self.redis.setex(banned_key, self.ban_duration, "1")
                self.redis.delete(error_key)  # Reset counter
                logger.warning(f"Banned IP {ip} for {self.ban_duration//60} minutes")

        except redis.exceptions.ResponseError as e:
            # Reset corrupted key if wrong type (e.g., string instead of number)
            if "WRONGTYPE" in str(e):
                self.redis.delete(error_key)
                logger.error(f"Reset corrupted key {error_key}")
            else:
                logger.error(f"Redis error: {str(e)}")

    def _get_client_ip(self, request):
        """Extract client IP from request."""
        return request.META.get("REMOTE_ADDR", "0.0.0.0")

class DemoTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_demo:
            token = request.auth
            if token and token.is_expired:
                logger.info(
                    f"Expired demo token for user {request.user.username}"
                )
                return JsonResponse(
                    {"detail": "Demo session expired"}, 
                    status=401
                )
        return self.get_response(request)

