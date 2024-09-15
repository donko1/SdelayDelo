from django.db import models

class Note(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    text = models.TextField()

    def __str__(self):
        return f"Note {self.id} by User {self.user_id}: {self.text[:20]}"
