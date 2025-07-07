from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="tasks.cleanup_demo_users")  
def cleanup_demo_users(self):
    """delete all demo-users older than 2 hours"""
    User = get_user_model()
    cutoff = timezone.now() - timezone.timedelta(hours=2)
    
    deleted_count, _ = User.objects.filter(
        is_demo=True,
        created_at__lt=cutoff
    ).delete()
    
    logger.info(f"Deleted {deleted_count} demo accounts")
    return deleted_count