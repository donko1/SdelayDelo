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

    Attributes:
    - email: The user's email address to which the token is associated.
    - code: A 6-digit verification code sent to the user.
    - token_hash: A hashed representation of the token for security purposes.
    - salt: A random unique string added to the token for secure hashing.
    - created_at: The datetime when the token was created.
    - expires_at: The datetime when the token will expire.
    - is_verified: A flag indicating whether the email has been successfully verified.
    """

    email = models.EmailField()
    code = models.CharField(max_length=6, editable=False)
    token_hash = models.CharField(max_length=64, editable=False, unique=True)
    salt = models.CharField(
        max_length=32, editable=False, default=get_random_string(32)
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=timezone.now() + timedelta(minutes=10))
    is_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        Overriding the save method to generate the verification code, token, and salt.
        """
        if not self.code:
            self.code = get_random_string(length=6, allowed_chars="0123456789")
        if not self.token_hash:
            raw_token = str(uuid.uuid4())  # Generate a unique raw token
            self.salt = get_random_string(32)  # Generate a unique salt
            self.token_hash = self.hash_token(raw_token, self.salt)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(
                days=1
            )  # Default expiration: 1 day
        super().save(*args, **kwargs)

    @staticmethod
    def hash_token(token, salt=None):
        """
        Creates a secure hash of the token using SHA256, a salt, and the app's secret key.

        Args:
        - token (str): The raw token to be hashed.
        - salt (str, optional): The salt to add randomness to the hash. If not provided, a new random salt will be generated.

        Returns:
        - tuple: A tuple containing the hash and the salt used.
        """
        salt = salt or ""
        secret_key = settings.SECRET_KEY.encode()
        token_with_salt = token.encode() + salt.encode()
        return hashlib.sha256(secret_key + token_with_salt).hexdigest(), salt

    def send_verification_email(self):
        """
        Sends a verification email containing the 6-digit code to the user's email address.
        """
        subject = "Verification Code for Your Account"
        message = f"Your verification code is: {self.code}"
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.email])

    def validate_email(self, code):
        """
        Validates the provided code and marks the email as verified if successful.

        Args:
        - code (str): The 6-digit verification code provided by the user.

        Returns:
        - bool: True if the code is correct and the token is not expired; False otherwise.
        """
        if self.code == code and timezone.now() <= self.expires_at:

            return True
        return False

    def __str__(self):
        """
        String representation of the model.
        """
        return f"TokenToEmail(email={self.email}, is_verified={self.is_verified})"
