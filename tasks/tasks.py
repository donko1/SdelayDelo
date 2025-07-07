from django_apscheduler import util
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)


@util.close_old_connections
def cleanup_demo_users():
    """delete all demo-users older than 2 hours"""
    User = get_user_model()

    cutoff = timezone.now() - timezone.timedelta(hours=2)
    
    deleted_count, _ = User.objects.filter(
        is_demo=True,
        created_at__lt=cutoff
    ).delete()
    
    logger.debug(f"Deleted {deleted_count} demo accounts")