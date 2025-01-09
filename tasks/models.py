from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

import hashlib
import uuid
from datetime import timedelta


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
    Model representing a verification token sent to an email address for registration.
    """

    email = models.EmailField(unique=True)
    code = models.CharField(max_length=6, editable=False)
    token_hash = models.CharField(max_length=64, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=timezone.now() + timedelta(days=1))
    is_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        Overriding the save method to generate the code and hash token before saving the model.
        """
        if not self.code:
            self.code = get_random_string(length=6, allowed_chars="0123456789")
        if not self.token_hash:
            # Generate a raw token and hash it
            raw_token = str(uuid.uuid4())  # Create a unique UUID token
            self.token_hash = self.hash_token(raw_token)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(
                days=1
            )  # Token expires in 1 day
        super().save(*args, **kwargs)

    @staticmethod
    def hash_token(token):
        """
        Creates a secure hash of the token using SHA256 with the app's secret key.

        Args:
        - token (str): Raw token to be hashed.

        Returns:
        - str: The hashed token.
        """

        secret_key = settings.SECRET_KEY.encode()
        return hashlib.sha256(secret_key + token.encode()).hexdigest()

    def send_verification_email(self):
        """
        Sends the verification code to the user's email.
        """
        subject = "Verification Code for Your Account"
        message = f"Your verification code is: {self.code}"
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.email])

    def validate_email(self, code):
        """
        Validates the provided verification code and marks the email as verified.

        Args:
        - code (str): Verification code provided by the user.

        Returns:
        - bool: True if the code matches and the token has not expired, otherwise False.
        """
        if self.code == code and timezone.now() <= self.expires_at:
            self.is_verified = True
            self.save(update_fields=["is_verified"])
            return True
        return False

    def __str__(self):
        return f"TokenToEmail(email={self.email}, is_verified={self.is_verified})"
