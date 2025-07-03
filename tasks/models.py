from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

import hashlib
import uuid
from datetime import timedelta
import logging
import random
import pytz

from .validators import validate_hex_color

logger = logging.getLogger(__name__)

def generate_hex_color():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    return f"#{r:02x}{g:02x}{b:02x}".upper()

def validate_timezone(value):
    if value not in pytz.all_timezones:
        raise ValidationError(f"{value} is not a valid timezone.")

def default_token_expiration():
    return timezone.now() + timedelta(minutes=10)


class UnarchivedNoteQuerySet(models.QuerySet):
    """Queryset for note to add unarchived and archived method"""
    def unarchived(self):
        return self.filter(is_archived=False)  # Чистый фильтр без автоархива

    def archived(self, user=None):
        qs = self.filter(is_archived=True)
        if user:
            qs = qs.filter(user=user)
        return qs



class NoteManager(models.Manager):
    """Manager for note to add unarchived and archived method"""

    def get_queryset(self):
        return UnarchivedNoteQuerySet(self.model, using=self._db)

    def unarchived(self):
        return self.get_queryset().unarchived()

    def archived(self, user=None):
        return self.get_queryset().archived(user=user)

    def clear_archive(self, user):
        archived_notes = self.archived(user=user)
        count = len(archived_notes)
        logger.debug(f"Deleting {count} for {user.username}")

        archived_notes.delete()

        return count

    def get_all(self):
        return super().get_queryset()


class custom_user(AbstractUser):

    LANGUAGE_CHOICES = (
        ("en", "English"),
        ("ru", "Russian"),
    )

    THEME_CHOICES = (
        ("light", "Light"),
        ("dark", "Dark"),
    )

    telegram_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    fa_2 = models.BooleanField(default=False)

    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default="en",
        verbose_name="Preferred Language",
        help_text="Choose your preferred language for the site.",
    )

    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default="light",
        verbose_name="Preferred Theme",
        help_text="Choose your preferred theme for the site (light or dark).",
    )

    timezone = models.CharField(
        max_length=50, default="UTC", validators=[validate_timezone]
    )

    def get_current_time(self):
        user_timezone = pytz.timezone(self.timezone)
        return timezone.now().astimezone(user_timezone)


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

    title = models.CharField(max_length=255, verbose_name="Заголовок")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="tags", verbose_name="Создатель"
    )
    colour = models.CharField(
        max_length=7, validators=[validate_hex_color], verbose_name="Цвет", blank=True
    )  # Hexadecimal color code
    icon = models.CharField(
        max_length=255, blank=True, null=True,  verbose_name="Иконка"
    )

    class Meta:
        verbose_name = "Тэг"
        verbose_name_plural = "Тэги"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """ Set colour if no color"""
        if not self.colour:
            self.colour = generate_hex_color()
            logger.debug("Generating random color")
        super().save(*args, **kwargs)



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
    - is_archived: status of archived or not the note. Default value is False
    """

    objects = NoteManager()

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notes", verbose_name="Создатель"
    )
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    description = models.TextField(verbose_name="Описание")
    date_create = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    date_changed = models.DateTimeField(auto_now=True, verbose_name="Дата изменения")
    date_of_note = models.DateField(blank=True, null=True, verbose_name="Дата заметки")
    tags = models.ManyToManyField(
        Tag, related_name="notes", blank=True, verbose_name="Тэги"
    )
    is_pinned = models.BooleanField(default=False, verbose_name="Статус закреплённости")

    is_archived = models.BooleanField(
        default=False,
        blank=False,
        null=False,
        verbose_name="Статус нахождения в архиве",
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Заметка"
        verbose_name_plural = "Заметки"
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

    email = models.EmailField(verbose_name="Почта")
    code = models.CharField(max_length=6, editable=False, verbose_name="Код")
    token_hash = models.CharField(
        max_length=64, editable=False, unique=True, verbose_name="Хэш токена"
    )
    salt = models.CharField(
        max_length=32,
        editable=False,
        default=get_random_string(32),
        verbose_name="Соль",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    expires_at = models.DateTimeField(
        default=default_token_expiration,
        verbose_name="Дата истечения токена",
    )
    is_verified = models.BooleanField(
        default=False, verbose_name="Статус подтверждения почты"
    )

    def save(self, *args, **kwargs):
        """
        Overriding the save method to generate the verification code, token, and salt. Removing all 
        """
        if not self.code:
            self.code = get_random_string(length=6, allowed_chars="0123456789")
            logger.debug(f"Generated verification code for {self.email}: {self.code}")
        if not self.token_hash:
            raw_token = str(uuid.uuid4())  # Generate a unique raw token
            self.salt = get_random_string(32)  # Generate a unique salt
            self.token_hash = self.hash_token(raw_token, self.salt)
            logger.debug(f"Generated token hash for {self.email}")

        self.__class__.objects.filter(email=self.email).exclude(pk=self.pk).delete()
        super().save(*args, **kwargs)
        logger.info(f"Saved TokenToEmail for {self.email}")

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
        hash_result = hashlib.sha256(secret_key + token_with_salt).hexdigest()
        logger.debug(f"Hashed token with salt: {salt}")
        return hash_result, salt

    def send_verification_email(self):
        """
        Sends a verification email containing the 6-digit code to the user's email address.
        """
        subject = "Verification Code for Your Account"
        message = f"Your verification code is: {self.code}"
        logger.debug(f"Sending verification code to {self.email}")
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.email])
        logger.info(f"Sent verification email to {self.email}")

    def validate_email(self, code):
        """
        Validates the provided code and marks the email as verified if successful.

        Args:
        - code (str): The 6-digit verification code provided by the user.

        Returns:
        - bool: True if the code is correct and the token is not expired; False otherwise.
        """
        logger.debug(f"now:{timezone.now()}; expires_at:{self.expires_at}")
        if self.code == code and timezone.now() <= self.expires_at:
            logger.info(f"Email {self.email} successfully verified")
            return True
        logger.debug(f"Invalid or expired code for {self.email}")
        return False

    def __str__(self):
        """
        String representation of the model.
        """
        return f"TokenToEmail(email={self.email}, is_verified={self.is_verified})"

    class Meta:
        verbose_name = "Токен для подтверждения почты"
        verbose_name_plural = "Токены для подтверждения почты"
