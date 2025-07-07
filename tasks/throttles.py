from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class WhoAmIRateThrottle(SimpleRateThrottle):
    scope = "whoami"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return f"throttle_{self.scope}_{request.user.id}"
        else:
            ident = self.get_ident(request)
            return f"throttle_{self.scope}_{ident}"


class NoteAndTagThrottleRead(UserRateThrottle):
    """
    Throttle for read operations (GET, HEAD, OPTIONS) for Note and Tag models.
    """

    scope = "note_and_tag_read"

    def allow_request(self, request, view):
        """
        Only allow read operations to be throttled by this class.
        """
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return super().allow_request(request, view)
        return True  # Allow other requests


class NoteAndTagThrottleWrite(UserRateThrottle):
    """
    Throttle for write operations (POST, PUT, PATCH, DELETE) for Note and Tag models.
    """

    scope = "note_and_tag_write"

    def allow_request(self, request, view):
        """
        Only allow write operations to be throttled by this class.
        """
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            return super().allow_request(request, view)
        return True  # Allow other requests


class CreateDemoUserThrottle(SimpleRateThrottle):
    """
    Throttle for creating demo-users
    """
    scope = "create-demo"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request) + request.META.get('HTTP_USER_AGENT', '')[:20]
        user_ident = request.user.pk if request.user.is_authenticated else None
        return f"throttle_{self.scope}_{user_ident or ident}"


class IconThrottle(SimpleRateThrottle):
    scope = "icon"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return f"throttle_user_{request.user.pk}"
        return None
