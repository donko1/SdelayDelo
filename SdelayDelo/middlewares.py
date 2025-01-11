from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now
from django.http import HttpResponse


class ErrorTrackingMiddleware:
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
        if response.status_code >= 400:
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
