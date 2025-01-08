from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings

import uuid

from .validators import validate_hex_color


class custom_user(AbstractUser):
    telegram_id = models.CharField(max_length=255, unique=True, null=True)


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
    colour = models.CharField(
        max_length=7, validators=[validate_hex_color]
    )  # Hexadecimal color code
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
    is_pinned = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-is_pinned"]


class TokenToEmail(models.Model):
    """
    This model is for creating token and key-code for register user
    Fields:
    - email: the email of the owner
    - code: code from 6 random integers that the user must write to confirm the email
    - token: access token to create/edit account
    - created_at: timestamp for when the token was created
    """

    email = models.EmailField(unique=True)
    code = models.CharField(max_length=6, editable=False)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = get_random_string(length=6, allowed_chars="0123456789")
        super().save(*args, **kwargs)

    def send_verification_email(self):
        """
        Sends a verification email to the user with the code.
        """
        subject = "Код для подтверждения SdelayDelo"
        message = f"Код для подтверждения почты: {self.code}"
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.email])

    def __str__(self):
        return f"TokenToEmail(email={self.email}, token={self.token})"
