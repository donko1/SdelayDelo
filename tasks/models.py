from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import now

User = get_user_model()


class Tag(models.Model):
    """
    Represents a tag that can be associated with notes.
    Fields:
    - title: The name of the tag.
    - user: The owner of the tag.
    - colour: The color associated with the tag (e.g., #FF0000).
    - icon: An optional icon name for the tag.
    """

    title = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tags")
    colour = models.CharField(max_length=7)  # Hexadecimal color code
    icon = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.title


class Note(models.Model):
    """
    Represents a note created by a user.
    Fields:
    - user: The owner of the note.
    - title: The title of the note.
    - description: The content of the note.
    - date_create: The date and time when the note was created.
    - date_changed: The date and time when the note was last modified.
    - tags: Tags associated with the note (many-to-many relationship).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=255)
    description = models.TextField()
    date_create = models.DateTimeField(auto_now_add=True)
    date_changed = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField(Tag, related_name="notes", blank=True)

    def __str__(self):
        return self.title
