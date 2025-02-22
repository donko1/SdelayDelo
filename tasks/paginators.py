from django.utils import timezone

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from datetime import timedelta
import logging

from .models import Note

logger = logging.getLogger(__name__)


class NotePagination(PageNumberPagination):
    """
    Custom pagination class that activates only for API version v2 and v3.
    - Default page size: 25
    - Client can override via `page_size` query param
    - Maximum allowed page size: 100
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        """Adding new param to ARCHIVED list: total_count_7_days"""

        response_data = super().get_paginated_response(data).data

        try:
            request = self.request
            url = request.get_full_path()
            if not request:
                logger.warning("No request object in pagination context")
                return Response(response_data)

            logger.debug("Url is " + url)

            if "archived" in url:
                user = request.user
                if not user.is_authenticated:
                    logger.warning("Unauthenticated user access")
                    return Response(response_data)

                now = timezone.now()
                seven_days_ago = now - timedelta(days=7)

                base_qs = Note.objects.filter(user=user, is_archived=True)

                total_count_7_days = (
                    base_qs.filter(
                        date_of_note__gte=seven_days_ago, date_of_note__lte=now
                    )
                    .exclude(date_of_note__isnull=True)
                    .count()
                )

                response_data.update(
                    {
                        "total_count_7_days": total_count_7_days,
                    }
                )
                logger.debug(f"Added stats: {total_count_7_days}")

        except Exception as e:
            logger.error(f"Pagination error: {str(e)}", exc_info=True)

        return Response(response_data)
