from rest_framework.throttling import SimpleRateThrottle


class WhoAmIRateThrottle(SimpleRateThrottle):
    scope = "whoami"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return f"throttle_{self.scope}_{request.user.id}"
        else:
            ident = self.get_ident(request)
            return f"throttle_{self.scope}_{ident}"
