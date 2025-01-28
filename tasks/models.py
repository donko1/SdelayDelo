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

from dateutil.relativedelta import relativedelta


from .validators import validate_hex_color


class custom_user(AbstractUser):
    telegram_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    fa_2 = models.BooleanField(default=False)


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


class Notification(models.Model):
    """
    Represents a user notification with scheduling and recurrence capabilities.

    Attributes:
        user (ForeignKey): Recipient of the notification
        title (CharField): Short description of the notification
        content (TextField): Detailed message content
        created_at (DateTimeField): Initial creation timestamp
        is_read (BooleanField): Read status flag
        is_repeating (BooleanField): Recurrence activation flag
        repeat_type (CharField): Type of recurrence pattern
        repeat_params (JSONField): Custom recurrence parameters
        next_notification_date (DateTimeField): Next scheduled occurrence
        last_notification_date (DateTimeField): Last actual dispatch time
        is_active (BooleanField): Active status flag
    """

    REPEAT_TYPES = (
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
        ("custom", "Custom Schedule"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="User",
        help_text="Recipient of the notification",
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Title",
        help_text="Short description (max 255 chars)",
    )
    content = models.TextField(
        verbose_name="Content", help_text="Detailed message body"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creation Date",
        help_text="Initial creation timestamp",
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name="Read Status",
        help_text="Has the user viewed the notification?",
    )
    is_repeating = models.BooleanField(
        default=False,
        verbose_name="Repeating",
        help_text="Does this notification recur?",
    )
    repeat_type = models.CharField(
        max_length=10,
        choices=REPEAT_TYPES,
        null=True,
        blank=True,
        verbose_name="Repeat Type",
        help_text="Select recurrence pattern",
    )
    repeat_params = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Repeat Parameters",
        help_text="Custom parameters in JSON format. For custom type, use: "
        '{"interval": number, "unit": "days|weeks|months|years"}',
    )
    next_notification_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Next Occurrence",
        help_text="Next scheduled dispatch time",
    )
    last_notification_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Sent",
        help_text="Timestamp of most recent dispatch",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Is this notification currently active?",
    )

    def __str__(self):
        """String representation of the notification"""
        return f"{self.title} - {self.user.username}"

    def save(self, *args, **kwargs):
        """
        Override save method to handle initial scheduling for repeating notifications.
        Sets next_notification_date if creating a new repeating notification.
        """
        if not self.pk and self.is_repeating:
            self.next_notification_date = self.created_at or timezone.now()
        super().save(*args, **kwargs)

    def update_next_notification(self):
        """
        Calculate and update the next scheduled date based on recurrence rules.
        Supports predefined intervals and custom parameters.
        """
        if not self.is_repeating or not self.is_active:
            return

        now = timezone.now()
        last_date = self.next_notification_date or now

        if self.repeat_type == "daily":
            next_date = last_date + relativedelta(days=1)
        elif self.repeat_type == "weekly":
            next_date = last_date + relativedelta(weeks=1)
        elif self.repeat_type == "monthly":
            next_date = last_date + relativedelta(months=1)
        elif self.repeat_type == "yearly":
            next_date = last_date + relativedelta(years=1)
        elif self.repeat_type == "custom" and self.repeat_params:
            # Custom interval handling
            interval = self.repeat_params.get("interval", 1)
            unit = self.repeat_params.get("unit", "days")
            if unit.endswith("s"):  # Ensure plural form
                unit = unit.rstrip("s")
            next_date = last_date + relativedelta(**{f"{unit}s": interval})
        else:
            return

        if next_date > now:
            self.next_notification_date = next_date
            self.save()

    def send_notification(self):
        """
        Main notification dispatch method.
        Should be extended with actual delivery logic (email, push, etc).
        Updates timestamps and handles recurrence scheduling.
        """
        # Implement actual delivery mechanism here
        # Example: send_email, push_to_websocket, etc

        self.last_notification_date = timezone.now()
        self.save()

        if self.is_repeating:
            self.update_next_notification()
        else:
            self.is_active = False
            self.save()

    class Meta:
        """Metadata options for the Notification model"""

        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["next_notification_date"]),
        ]
        ordering = ["-created_at"]
