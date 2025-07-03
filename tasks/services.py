import pytz
from django.utils import timezone
from .models import Note

class NoteArchiver:
    @classmethod
    def archive_user_notes(cls, user):
        """Auto arcgive old notes with user timezone."""
        if not user.timezone:
            raise ValueError("User has no timezone set!")

        try:
            user_tz = pytz.timezone(user.timezone)
        except pytz.UnknownTimeZoneError:
            user_tz = timezone.utc  

        today = timezone.now().astimezone(user_tz).date()
        
        updated = (
            Note.objects
            .filter(user=user, is_archived=False, date_of_note__lt=today)
            .update(is_archived=True)
        )
        
        return updated  