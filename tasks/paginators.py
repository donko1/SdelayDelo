from rest_framework.pagination import PageNumberPagination


class VersionedPagination(PageNumberPagination):
    """
    Custom pagination class that activates only for API version v2.
    - Default page size: 25
    - Client can override via `page_size` query param
    - Maximum allowed page size: 100
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate queryset only if request version is v2.
        Returns None for other versions to disable pagination.
        """
        if request.version == "v2":
            return super().paginate_queryset(queryset, request, view)
        return None
