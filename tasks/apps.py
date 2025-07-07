from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'

    def ready(self):
        import sys
        if 'makemigrations' in sys.argv or 'migrate' in sys.argv:
            return

        try:
            from django_apscheduler.schedulers.background import BackgroundScheduler
            from django_apscheduler.jobstores import DjangoJobStore
            from .tasks import cleanup_demo_users
            
            scheduler = BackgroundScheduler()
            scheduler.add_jobstore(DjangoJobStore(), "default")
            
            scheduler.add_job(
                cleanup_demo_users,
                'interval',
                hours=2,
                id="demo_cleanup",
                replace_existing=True,
            )
            
            scheduler.start()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")