from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import IntegrityError

from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token

import uuid
import datetime
import io
import os
import pytz

from PIL import Image

from SdelayDelo.settings import TESTING

from .models import Note, Tag, TokenToEmail
from .serializers import TagSerializer, NoteSerializer, IconUploadSerializer
from .validators import is_hex_color
from .views import who_am_i


def aware_datetime(dt):
    """
    Ensure a datetime object is timezone-aware.
    """
    parsed = parse_datetime(dt)
    if parsed and is_naive(parsed):
        return make_aware(parsed)
    return parsed


def generate_test_image(filename="test.png", size=(100, 100), color=(155, 0, 0)):
    """
    Generate a simple image file for testing purposes.
    """
    file_obj = io.BytesIO()
    image = Image.new("RGB", size, color)
    image.save(file_obj, "PNG")
    file_obj.seek(0)
    return SimpleUploadedFile(filename, file_obj.read(), content_type="image/png")


User = get_user_model()


class CustomUserModelTests(TestCase):
    """
    Tests for verifying the functionality of the custom user model (custom_user).
    """

    def setUp(self):
        """
        Set up for each test.
        """
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testuser",
            password="testpassword",
            email="test@example.com",
            telegram_id="123456789",
            fa_2=True,
            language="ru",
            theme="dark",
        )

    def test_user_creation(self):
        """
        Verifies successful user creation.
        """
        user = self.user

        self.assertTrue(self.User.objects.filter(username="testuser").exists())

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpassword"))
        self.assertEqual(user.telegram_id, "123456789")
        self.assertTrue(user.fa_2)
        self.assertEqual(user.language, "ru")
        self.assertEqual(user.theme, "dark")

    def test_default_values(self):
        """
        Verifies the default values for the language and theme fields.
        """
        user = self.User.objects.create_user(
            username="defaultuser", password="password"
        )

        self.assertEqual(user.language, "en")
        self.assertEqual(user.theme, "light")
        self.assertFalse(user.fa_2)
        self.assertIsNone(user.telegram_id)

    def test_language_choices(self):
        """
        Verifies the constraint of values for the language field.
        """
        user = self.User(
            username="invaliduser", password="password", language="invalid"
        )
        with self.assertRaises(DjangoValidationError) as context:
            user.full_clean()
        self.assertIn(
            "Значения 'invalid' нет среди допустимых вариантов.",
            context.exception.message_dict["language"],
        )

    def test_theme_choices(self):
        """
        Verifies the constraint of values for the theme field.
        """
        user = self.User(username="invaliduser", password="password", theme="invalid")
        with self.assertRaises(DjangoValidationError) as context:
            user.full_clean()
        self.assertIn(
            "Значения 'invalid' нет среди допустимых вариантов.",
            context.exception.message_dict["theme"],
        )

    def test_telegram_id_unique(self):
        """
        Verifies the uniqueness of the telegram_id field.

        Since unique constraints raise IntegrityError on database level during `save()`,
        we test for that.
        """
        self.User.objects.create_user(
            username="user1", password="password", telegram_id="duplicate_id"
        )
        with self.assertRaises(IntegrityError):  # Expect IntegrityError during save
            user2 = self.User(
                username="user2", password="password", telegram_id="duplicate_id"
            )
            user2.save()  # Save triggers the database-level unique constraint check

    def test_string_representation(self):
        """
        Verifies the string representation of the user (__str__).
        """
        self.assertEqual(str(self.user), "testuser")

    def test_telegram_id_nullable(self):
        """
        Verifies that the telegram_id field can be None (null=True).
        """
        user = self.User.objects.create_user(
            username="nullableuser", password="password"
        )
        self.assertIsNone(user.telegram_id)

    def test_telegram_id_blankable(self):
        """
        Verifies that the telegram_id field can be an empty string (blank=True).
        """
        user = self.User.objects.create_user(
            username="blankuser", password="password", telegram_id=""
        )
        self.assertEqual(user.telegram_id, "")

    def test_get_current_time(self):
        """
        Verifies that the get_current_time method returns the correct time for the user's timezone.
        """
        user = self.User.objects.create_user(
            username="timezoneuser", password="password", timezone="Europe/Moscow"
        )

        # Get the current time in the user's timezone
        user_time = user.get_current_time()

        # Get the current time in UTC and convert it to the user's timezone
        utc_time = timezone.now()
        moscow_tz = pytz.timezone("Europe/Moscow")
        expected_time = utc_time.astimezone(moscow_tz)

        # Compare the times (allowing for a small difference due to execution time)
        self.assertAlmostEqual(user_time, expected_time, delta=timedelta(seconds=1))

    def test_timezone_default(self):
        """
        Verifies that the default timezone is UTC.
        """
        user = self.User.objects.create_user(
            username="defaulttimezoneuser", password="password"
        )
        self.assertEqual(user.timezone, "UTC")

    def test_invalid_timezone(self):
        """
        Verifies that an invalid timezone raises a ValidationError.
        """
        with self.assertRaises(DjangoValidationError):
            user = self.User(
                username="invalidtimezoneuser",
                password="password",
                timezone="Invalid/Timezone",
            )
            user.full_clean()

    def test_fa_2_default(self):
        """
        Verifies that the default value for fa_2 is False.
        """
        user = self.User.objects.create_user(
            username="fa2defaultuser", password="password"
        )
        self.assertFalse(user.fa_2)

    def test_telegram_id_max_length(self):
        """
        Verifies that the telegram_id field has a maximum length of 255 characters.
        """
        max_length = 255
        telegram_id = "a" * (max_length + 1)

        with self.assertRaises(DjangoValidationError):
            user = self.User(
                username="telegramuser", password="password", telegram_id=telegram_id
            )
            user.full_clean()

    def test_get_current_time_different_timezones(self):
        """
        Verifies that get_current_time returns different times for users in different timezones.
        """
        user1 = self.User.objects.create_user(
            username="user1", password="password", timezone="America/New_York"
        )
        user2 = self.User.objects.create_user(
            username="user2", password="password", timezone="Asia/Tokyo"
        )

        time1 = user1.get_current_time()
        time2 = user2.get_current_time()

        self.assertNotEqual(time1.tzinfo, time2.tzinfo)
        self.assertNotEqual(time1.hour, time2.hour)


class TestHexColorValidation(TestCase):
    """This test case tests if is_hex_color func works correct"""

    def test_valid_hex_colors(self):
        self.assertTrue(is_hex_color("#FFFFFF"))
        self.assertTrue(is_hex_color("#123ABC"))
        self.assertTrue(is_hex_color("#b55353"))

    def test_invalid_hex_colors(self):
        self.assertFalse(is_hex_color("123ABC"))
        self.assertFalse(is_hex_color("#ZZZ"))
        self.assertFalse(is_hex_color("#12345"))
        self.assertFalse(is_hex_color("#12345G"))


class HelloWorldViewTest(TestCase):
    def test_hello_world_returns_correct_json(self):
        """
        Check if GET to hello_world returns correct JSON.
        """
        response = self.client.get(reverse("hello_world"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"content": "Hello world!"})

    def test_hello_world_rejects_post(self):
        """
        Check if POST to hello_world return error 405 (Method Not Allowed).
        """
        response = self.client.post(reverse("hello_world"))
        self.assertEqual(response.status_code, 405)


class TagModelTest(TestCase):
    """Tests for the Tag model."""

    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username="testuser", password="testpassword"
        )

    def test_create_tag(self):
        """Test that a Tag can be created successfully."""
        tag = Tag.objects.create(
            title="Urgent", user=self.user, colour="#FF0000", icon="exclamation"
        )
        self.assertEqual(tag.title, "Urgent")
        self.assertEqual(tag.user, self.user)
        self.assertEqual(tag.colour, "#FF0000")
        self.assertEqual(tag.icon, "exclamation")

    def test_tag_without_icon(self):
        """Test that a Tag can be created without an icon."""
        tag = Tag.objects.create(title="General", user=self.user, colour="#CCCCCC")
        self.assertEqual(tag.title, "General")
        self.assertEqual(tag.user, self.user)
        self.assertEqual(tag.colour, "#CCCCCC")
        self.assertIsNone(tag.icon)

    def test_tag_str_representation(self):
        """Test the string representation of a Tag."""
        tag = Tag.objects.create(title="Important", user=self.user, colour="#FF0000")
        self.assertEqual(str(tag), "Important")

    def test_valid_hex_color(self):
        """
        The model should accept a valid HEX color.
        """
        tag = Tag(title="Test Tag", colour="#25a3ed", user=self.user)
        tag.full_clean()

    def test_invalid_hex_color(self):
        """
        The model should reject an invalid HEX color.
        """
        tag = Tag(title="Test Tag", colour="123ABC", user=self.user)
        with self.assertRaises(DjangoValidationError):
            tag.full_clean()


class NoteModelTest(TestCase):
    """Tests for the Note model."""

    def setUp(self):
        # Create a test user and tags
        self.user = User.objects.create_user(
            username="testuser", password="testpassword"
        )
        self.tag1 = Tag.objects.create(title="Work", user=self.user, colour="#0000FF")
        self.tag2 = Tag.objects.create(
            title="Personal", user=self.user, colour="#00FF00"
        )

    def test_create_note(self):
        """Test that a Note can be created successfully."""
        note = Note.objects.create(
            user=self.user,
            title="Meeting Notes",
            description="Discuss project deadlines.",
        )
        note.tags.add(self.tag1, self.tag2)

        self.assertEqual(note.user, self.user)
        self.assertEqual(note.title, "Meeting Notes")
        self.assertEqual(note.description, "Discuss project deadlines.")
        self.assertIn(self.tag1, note.tags.all())
        self.assertIn(self.tag2, note.tags.all())

    def test_unarchived_notes(self):
        """
        Test that the 'unarchived' method returns only non-archived notes.
        """

        note1 = Note.objects.create(
            user=self.user,
            title="Note 1",
            description="Description 1",
            is_archived=False,
        )
        note2 = Note.objects.create(
            user=self.user,
            title="Note 2",
            description="Description 2",
            is_archived=True,
        )
        note3 = Note.objects.create(
            user=self.user,
            title="Note 3",
            description="Description 3",
            is_archived=False,
        )

        unarchived_notes = Note.objects.unarchived()

        self.assertEqual(unarchived_notes.count(), 2)
        for note in unarchived_notes:
            self.assertFalse(note.is_archived)
        self.assertIn(note1, unarchived_notes)
        self.assertIn(note3, unarchived_notes)
        self.assertNotIn(note2, unarchived_notes)

    def test_archived_notes(self):
        """
        Test that the 'archived' method returns only archived notes.
        """
        note1 = Note.objects.create(
            user=self.user,
            title="Note 1",
            description="Description 1",
            is_archived=False,
        )
        note2 = Note.objects.create(
            user=self.user,
            title="Note 2",
            description="Description 2",
            is_archived=True,
        )
        note3 = Note.objects.create(
            user=self.user,
            title="Note 3",
            description="Description 3",
            is_archived=False,
        )
        archived_notes = Note.objects.archived()
        self.assertEqual(archived_notes.count(), 1)
        for note in archived_notes:
            self.assertTrue(note.is_archived)
        self.assertIn(note2, archived_notes)
        self.assertNotIn(note1, archived_notes)
        self.assertNotIn(note3, archived_notes)

    def test_note_timestamps(self):
        """Test that Note timestamps are set correctly."""
        note = Note.objects.create(
            user=self.user,
            title="Meeting Notes",
            description="Discuss project deadlines.",
        )
        self.assertIsNotNone(note.date_create)
        self.assertIsNotNone(note.date_changed)

        # Simulate an update
        note.title = "Updated Title"
        note.save()
        self.assertNotEqual(note.date_create, note.date_changed)

    def test_note_without_tags(self):
        """Test that a Note can be created without tags."""
        note = Note.objects.create(
            user=self.user,
            title="Standalone Note",
            description="This note has no tags.",
        )
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.title, "Standalone Note")
        self.assertEqual(note.description, "This note has no tags.")
        self.assertEqual(note.tags.count(), 0)

    def test_note_str_representation(self):
        """Test the string representation of a Note."""
        note = Note.objects.create(
            user=self.user,
            title="Sample Note",
            description="A sample note for testing.",
        )
        self.assertEqual(str(note), "Sample Note")

    def test_note_with_multiple_tags(self):
        """Test that a Note can have multiple tags assigned and tests if is_archived field is working."""
        note = Note.objects.create(
            user=self.user,
            title="Tagged Note",
            description="This note is tagged.",
            is_archived=True,
        )
        note.tags.add(self.tag1, self.tag2)
        self.assertEqual(note.tags.count(), 2)
        self.assertIn(self.tag1, note.tags.all())
        self.assertIn(self.tag2, note.tags.all())

    def test_note_tag_filter(self):
        """Test that notes can be filtered by tags."""
        note1 = Note.objects.create(
            user=self.user, title="Work Note", description="Work-related tasks."
        )
        note2 = Note.objects.create(
            user=self.user, title="Personal Note", description="Personal-related tasks."
        )
        note1.tags.add(self.tag1)
        note2.tags.add(self.tag2)

        work_notes = Note.objects.filter(tags=self.tag1)
        personal_notes = Note.objects.filter(tags=self.tag2)

        self.assertIn(note1, work_notes)
        self.assertIn(note2, personal_notes)
        self.assertNotIn(note1, personal_notes)
        self.assertNotIn(note2, work_notes)

    def test_note_is_ordering_by_pinning(self):
        """Test if model base ordering by pinning and base value of is_pinned is false"""
        note1 = Note.objects.create(
            user=self.user, title="Test-note-1", description="some description-1."
        )
        note2 = Note.objects.create(
            user=self.user, title="Test-note-2", description="some description-2"
        )
        note3 = Note.objects.create(
            user=self.user,
            title="Test-note-3",
            description="some description-3",
            date_of_note=datetime.datetime.now(),
        )
        note4 = Note.objects.create(
            user=self.user,
            title="Test-note-4",
            description="some description-4",
        )

        note2.is_pinned = True
        note3.is_pinned = True

        note2.save()
        note3.save()

        self.assertTrue(note2.is_pinned)
        self.assertFalse(note1.is_pinned)

        self.assertEqual(
            list(Note.objects.all()), list(Note.objects.order_by("-is_pinned"))
        )


# class NotificationModelTests(TestCase): # TODO: check models.py
#     def setUp(self):
#         self.user = User.objects.create_user(username="testuser", password="12345")
#         self.notification_data = {
#             "user": self.user,
#             "title": "Test Notification",
#             "content": "This is a test notification.",
#             "is_repeating": True,
#             "repeat_type": "daily",
#             "repeat_params": None,
#             "is_active": True,
#         }

#     def create_notification(self, **kwargs):
#         data = {**self.notification_data, **kwargs}
#         return Notification.objects.create(**data)

#     def test_str_representation(self):
#         """
#         Test the string representation of the Notification model.
#         It should return the title and username of the user.
#         """
#         notification = self.create_notification()
#         expected_str = f"{notification.title} - {notification.user.username}"
#         self.assertEqual(str(notification), expected_str)

#     def test_update_next_notification_daily(self):
#         """
#         Test the update_next_notification method for daily repeat type.
#         The next_notification_date should be incremented by one day.
#         """
#         notification = self.create_notification(repeat_type="daily")
#         initial_next_date = notification.next_notification_date
#         notification.update_next_notification()
#         self.assertEqual(
#             notification.next_notification_date, initial_next_date + timedelta(days=1)
#         )

#     def test_update_next_notification_weekly(self):
#         """
#         Test the update_next_notification method for weekly repeat type.
#         The next_notification_date should be incremented by one week.
#         """
#         notification = self.create_notification(repeat_type="weekly")
#         initial_next_date = notification.next_notification_date
#         notification.update_next_notification()
#         self.assertEqual(
#             notification.next_notification_date, initial_next_date + timedelta(weeks=1)
#         )

#     def test_update_next_notification_monthly(self):
#         """
#         Test the update_next_notification method for monthly repeat type.
#         The next_notification_date should be incremented by one month.
#         """
#         notification = self.create_notification(repeat_type="monthly")
#         initial_next_date = notification.next_notification_date
#         notification.update_next_notification()
#         self.assertEqual(
#             notification.next_notification_date,
#             initial_next_date + relativedelta(months=1),
#         )

#     def test_update_next_notification_yearly(self):
#         """
#         Test the update_next_notification method for yearly repeat type.
#         The next_notification_date should be incremented by one year.
#         """
#         notification = self.create_notification(repeat_type="yearly")
#         initial_next_date = notification.next_notification_date
#         notification.update_next_notification()
#         self.assertEqual(
#             notification.next_notification_date,
#             initial_next_date + relativedelta(years=1),
#         )

#     def test_non_repeating_notification_deactivation(self):
#         """
#         Test that a non-repeating notification gets deactivated after sending.
#         """
#         notification = self.create_notification(is_repeating=False)
#         notification.send_notification()
#         self.assertFalse(notification.is_active)


class TagSerializerTestCase(APITestCase):
    """
    Test case for the TagSerializer.

    This class contains tests for validating and ensuring the correctness of
    the TagSerializer, which now gets the user from the request context.
    """

    def setUp(self):
        """
        Set up test data for the TagSerializer tests.

        Creates a user instance and initializes valid and invalid tag data.
        """
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.valid_tag_data = {
            "title": "Test Tag",
            "colour": "#FFFFFF",
            "icon": "icon.png",
        }
        self.invalid_tag_data = {
            "title": "Test Tag",
            "colour": "InvalidColor",
        }

    def test_valid_tag_serializer(self):
        """
        Test case for a valid tag serializer.

        Ensures that the serializer successfully validates data and the
        validated data matches the input. Also checks if user is added correctly from the request
        """
        request = self.factory.post(
            reverse("tag-list"), data=self.valid_tag_data, format="json"
        )
        request.user = self.user
        serializer = TagSerializer(
            data=self.valid_tag_data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["title"], self.valid_tag_data["title"]
        )
        self.assertEqual(
            serializer.validated_data["colour"], self.valid_tag_data["colour"]
        )
        self.assertEqual(serializer.validated_data["icon"], self.valid_tag_data["icon"])

    def test_invalid_tag_serializer(self):
        """
        Test case for an invalid tag serializer.

        Ensures that the serializer identifies invalid data as not valid.
        """
        request = self.factory.post(
            reverse("tag-list"), data=self.invalid_tag_data, format="json"
        )
        request.user = self.user
        serializer = TagSerializer(
            data=self.invalid_tag_data, context={"request": request}
        )
        self.assertFalse(serializer.is_valid())

    def test_tag_serializer_missing_fields(self):
        """
        Test case for a tag serializer with missing fields.

        Ensures that the serializer raises ValidationError when required
        fields are missing.
        """
        incomplete_data = {"title": "Incomplete Tag"}
        request = self.factory.post(
            reverse("tag-list"), data=incomplete_data, format="json"
        )
        request.user = self.user
        serializer = TagSerializer(data=incomplete_data, context={"request": request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("colour", serializer.errors)

    def test_valid_hex_color(self):
        """
        The serializer should accept a valid HEX color.
        """
        data = {"title": "Test Tag", "colour": "#123ABC"}
        request = self.factory.post(reverse("tag-list"), data=data, format="json")
        request.user = self.user
        serializer = TagSerializer(data=data, context={"request": request})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_hex_color(self):
        """
        The serializer should reject an invalid HEX color.
        """
        data = {"title": "Test Tag", "colour": "123ABC"}
        request = self.factory.post(reverse("tag-list"), data=data, format="json")
        request.user = self.user
        serializer = TagSerializer(data=data, context={"request": request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("colour", serializer.errors)
        self.assertEqual(serializer.errors["colour"][0], "Invalid HEX color code.")


@override_settings(LANGUAGE_CODE="en")
class NoteSerializerTestCase(APITestCase):
    """
    Test case for the NoteSerializer.

    This class contains tests for validating and ensuring the correctness of
    the NoteSerializer.
    """

    def setUp(self):
        """
        Set up test data for the NoteSerializer tests.

        Creates a user, a tag, and note instances. Initializes valid and
        invalid note data.
        """
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.access_token = Token.objects.create(user=self.user).key
        self.header = {"Authorization": f"Token {self.access_token}"}
        self.another_user = User.objects.create_user(
            username="anotheruser", password="password123"
        )
        self.tag = Tag.objects.create(
            title="Test Tag", colour="#FF5733", user=self.user
        )
        self.valid_note_data = {
            "title": "Test Note",
            "description": "This is a test note.",
            "tags": [self.tag.id],
            "date_of_note": "31/1/2024",
        }
        self.invalid_note_data = {
            "title": "",
            "description": "This is a test note.",
        }
        self.note = Note.objects.create(
            user=self.user,
            title="Existing Note",
            description="An existing note description.",
        )

    def get_serializer_context(self, user=None):
        if not user:
            user = self.user
        request = self.factory.get("/", headers=self.header)
        request.user = user
        return {"request": request}

    def test_valid_note_serializer(self):
        """
        Test case for a valid note serializer.

        Ensures that the serializer successfully validates data and the
        validated data matches the input.
        """
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=self.valid_note_data
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(
            serializer.validated_data["title"], self.valid_note_data["title"]
        )
        self.assertEqual(
            serializer.validated_data["description"],
            self.valid_note_data["description"],
        )

    def test_invalid_note_serializer(self):
        """
        Test case for an invalid note serializer.

        Ensures that the serializer raises a ValidationError when
        invalid data is provided.
        """
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=self.invalid_note_data
        )
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn("This field may not be blank.", str(context.exception))

    def test_note_serializer_update(self):
        """
        Test case for updating a note using the NoteSerializer.

        Ensures that the serializer updates the note instance correctly
        and updates the date_changed field to a new value.
        """
        updated_data = {
            "title": "Updated Note",
            "description": "Updated description.",
        }
        old_date_changed = self.note.date_changed
        serializer = NoteSerializer(
            instance=self.note,
            context=self.get_serializer_context(),
            data=updated_data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated_note = serializer.save()

        self.assertEqual(updated_note.title, updated_data["title"])
        self.assertEqual(updated_note.description, updated_data["description"])
        self.assertTrue(updated_note.date_changed > updated_note.date_create)
        self.assertTrue(updated_note.date_changed > old_date_changed)

    def test_note_serializer_with_tags(self):
        """
        Test case for a note serializer with associated tags.

        Ensures that the serializer correctly validates and serializes
        tags data.
        """
        data_with_tags = {
            "title": "Tagged Note",
            "description": "A note with tags.",
            "tags": [self.tag.id],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=data_with_tags
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        self.assertEqual(validated_data["title"], data_with_tags["title"])
        self.assertEqual(validated_data["description"], data_with_tags["description"])
        self.assertIn(self.tag.id, [tag.id for tag in validated_data["tags"]])

    def test_null_description(self):
        """Test if description can be null or absent"""
        data_with_null_description = {
            "title": "Note with null description",
            "tags": [self.tag.id],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=data_with_null_description
        )
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn("This field is required.", str(context.exception))

        data_without_description = {
            "title": "Note without description",
            "tags": [self.tag.id],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=data_without_description
        )
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn("This field is required.", str(context.exception))

    def test_empty_tags(self):
        """Test if note can be created without tags"""
        data_without_tags = {
            "title": "Note without tags",
            "description": "Description of a note without tags",
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=data_without_tags
        )
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn("This field is required.", str(context.exception))

    def test_invalid_tag_id(self):
        """Test if note can not be created with invalid tag id"""
        invalid_tag_data = {
            "title": "Note with invalid tag",
            "description": "Description with invalid tag",
            "tags": [9999],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=invalid_tag_data
        )
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn(
            'Invalid pk "9999" - object does not exist.', str(context.exception)
        )

    def test_note_serializer_create(self):
        """Test if create method works properly"""
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=self.valid_note_data
        )
        serializer.is_valid(raise_exception=True)
        note = serializer.save()
        self.assertEqual(note.title, self.valid_note_data["title"])
        self.assertEqual(note.description, self.valid_note_data["description"])
        self.assertEqual(note.user, self.user)
        self.assertIn(self.tag, note.tags.all())

    def test_note_serializer_update_with_tags(self):
        """Test if update method works properly with tags"""
        updated_data = {
            "title": "Updated Note with tags",
            "description": "Updated description with tags",
            "tags": [],
        }
        tag_2 = Tag.objects.create(title="Test Tag 2", colour="#000000", user=self.user)
        updated_data["tags"] = [tag_2.id]
        serializer = NoteSerializer(
            instance=self.note,
            context=self.get_serializer_context(),
            data=updated_data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated_note = serializer.save()
        self.assertIn(tag_2, updated_note.tags.all())

    def test_read_only_fields(self):
        """Test that read only fields cannot be updated"""
        data = {"date_create": "2023-01-01"}
        serializer = NoteSerializer(
            instance=self.note,
            context=self.get_serializer_context(self.another_user),
            data=data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated_note = serializer.save()
        self.assertNotEqual(updated_note.date_create, data["date_create"])
        self.assertEqual(updated_note.user, self.user)

    def test_invalid_data_types(self):
        """Test if serializer will throw error with invalid types of data"""
        invalid_types_data = {
            "title": "Invalid types data",
            "description": "Description of invalid types data",
            "tags": "invalid",
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=invalid_types_data
        )
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn(
            'Expected a list of items but got type "str".', str(context.exception)
        )

    def test_many_tags(self):
        """Test if serializer can create note with many tags"""
        tags = []
        for i in range(5):
            tags.append(
                Tag.objects.create(
                    title=f"Test tag {i}", colour="#000000", user=self.user
                )
            )

        valid_data_with_many_tags = {
            "title": "Note with many tags",
            "description": "Description of a note with many tags",
            "tags": [tag.id for tag in tags],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=valid_data_with_many_tags
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(len(serializer.validated_data["tags"]), 5)

    def test_long_title(self):
        """Test if serializer validates the length of title fields."""
        long_title_data = {
            "title": "A" * 300,
            "description": "Test description",
            "tags": [self.tag.id],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=long_title_data
        )
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn(
            "Ensure this field has no more than 255 characters.",
            str(context.exception),
        )
        self.assertIn("max_length", str(serializer.errors))

    def test_empty_title_with_blank_true(self):
        """Test if serializer can create title with blank=True"""
        if not NoteSerializer().fields["title"].allow_blank:
            self.skipTest("Test can be skipped because title is not allow_blank")
        empty_title_data = {
            "title": "",
            "description": "Description with empty title",
            "tags": [self.tag.id],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=empty_title_data
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["title"], "")

    def test_create_without_user_id(self):
        """Test if user can create note without user_id"""
        valid_data_without_user = {
            "title": "Title without user",
            "description": "Description without user",
            "tags": [self.tag.id],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=valid_data_without_user
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["user"], self.user)


if settings.EMAIL_EXISTS:

    class EmailVerificationTests(APITestCase):

        def setUp(self):
            """
            This view need not to get ban by too many requests after /SdelayDelo/tests.py tests
            """
            settings.ERROR_THRESHOLD = 100_000
            settings.ERROR_WINDOW_MINUTES = 0
            settings.BAN_DURATION_MINUTES = 100_000

        def test_check_if_email_registered(self):
            if settings.DEBUG:
                url = reverse("check_if_email_registered")
                # Test missing email
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

                # Test unregistered email
                response = self.client.get(url, {"email": "test@example.com"})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertFalse(response.data["email_is_registered"])

                # Test registered email
                User.objects.create_user(
                    username="testuser", email="test@example.com", password="password"
                )
                response = self.client.get(url, {"email": "test@example.com"})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertTrue(response.data["email_is_registered"])

        def test_send_verification_code(self):
            url = reverse("send_code")
            # Test missing email
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test valid email
            response = self.client.post(url, {"email": "test@example.com"})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(
                TokenToEmail.objects.filter(email="test@example.com").exists()
            )

        def test_verify_code(self):
            url = reverse("check_code")
            token_obj = TokenToEmail.objects.create(email="test@example.com")
            # Test missing data
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test invalid code
            response = self.client.post(
                url, {"email": "test@example.com", "code": "123456"}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test valid code
            response = self.client.post(
                url, {"email": "test@example.com", "code": token_obj.code}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("token", response.data)

        def test_register_user(self):
            url = reverse("register")
            token_obj = TokenToEmail.objects.create(
                email="test@example.com", is_verified=True
            )
            raw_token = str(uuid.uuid4())
            token_obj.token_hash = TokenToEmail.hash_token(raw_token)
            token_obj.save()

            # Test missing token
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test invalid token
            response = self.client.post(url, {"token": "invalid_token"})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test expired token
            token_obj.expires_at = now() - timedelta(days=1)
            token_obj.save()
            response = self.client.post(url, {"token": raw_token})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test valid token
            token_obj.expires_at = now() + timedelta(days=1)
            token_obj.save()
            response = self.client.post(
                url,
                {
                    "token": raw_token,
                    "username": "testuser",
                    "password": "password",
                    "email": "example@example.com",
                },
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertTrue(User.objects.filter(username="testuser").exists())

        def test_reset_password(self):
            """
            Tests if correct reset_password
            """
            url = reverse("reset_password")
            token_obj = TokenToEmail.objects.create(
                email="test@example.com", is_verified=True
            )
            User.objects.create(
                email="test@example.com", username="testuser", password="qwerty123"
            )
            raw_token = str(uuid.uuid4())
            token_obj.token_hash = TokenToEmail.hash_token(raw_token)
            token_obj.save()

            # Test missing token
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test invalid token
            response = self.client.post(url, {"token": "invalid_token"})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test expired token
            token_obj.expires_at = now() - timedelta(days=1)
            token_obj.save()
            response = self.client.post(url, {"token": raw_token})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test valid token
            token_obj.expires_at = now() + timedelta(days=1)
            token_obj.save()
            response = self.client.post(
                url,
                {"token": raw_token, "new_password": "testnewpassworD123"},
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(
                check_password(
                    "testnewpassworD123",
                    User.objects.filter(username="testuser")[0].password,
                )
            )

        def test_login(self):
            """
            Test login with login view
            """
            url = reverse("login")
            password = "testpassword123"
            hashed_password = make_password(password)

            user = User.objects.create(username="testuser", password=hashed_password)

            # Test incorrect password
            response = self.client.post(
                url, {"username": "testuser", "password": "incorrect_password"}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test not full data
            response = self.client.post(url, {"username": "testuser"})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test correct user and password
            response = self.client.post(
                url, {"username": "testuser", "password": password}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("access_token", response.data)

        def test_login_with_email(self):
            """
            Test login with email
            """
            url = reverse("login")
            password = "testpassword123"
            hashed_password = make_password(password)

            user = User.objects.create(
                username="testuser",
                password=hashed_password,
                email="example@example.com",
            )

            # Test incorrect password
            response = self.client.post(
                url, {"email": "example@example.com", "password": "incorrect_password"}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test not full data
            response = self.client.post(url, {"email": "example@example.com"})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            # Test correct user and password
            response = self.client.post(
                url, {"email": "example@example.com", "password": password}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("access_token", response.data)

        def test_login_with_2_fa(self):
            """
            Tests if correct login with 2fa
            """
            url = reverse("login")
            url_check_code = reverse("check_code")
            check_token_url = reverse("login")
            
            password = "qwerty123"
            hashed_password = make_password(password)

            User.objects.create(
                email="test@example.com",
                username="testuser",
                password=hashed_password,
                fa_2=True,
            )

            response = self.client.post(
                url,
                {"email": "test@example.com", "password": password},
            )
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertIn(
                f"Now visit {url_check_code} to continue", response.data["detail"]
            )
            self.assertEqual(f"t**t@example.com", response.data["email"])


            token_obj = TokenToEmail.objects.create(
                email="test@example.com", is_verified=True
            )
            raw_token = str(uuid.uuid4())
            token_obj.token_hash = TokenToEmail.hash_token(raw_token)
            token_obj.save()
            
            response = self.client.post(
                check_token_url, {"email": "test@example.com", "token": raw_token}
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("access_token", response.data)


class WhoAmIViewTest(APITestCase):

    def setUp(self):
        """
        Set up method to prepare the necessary resources for the tests.
        This method creates a user without a token, a user with a token,
        and obtains the endpoint url.
        """
        self.User = get_user_model()

        # Create user without token
        self.user = self.User.objects.create_user(
            username="testuser_no_token",
            password="testpassword",
            email="test_no_token@example.com",
        )
        # Create user with token
        self.user_with_token = self.User.objects.create_user(
            username="testuser_with_token",
            password="testpassword",
            email="test_with_token@example.com",
        )
        self.access_token = Token.objects.create(user=self.user_with_token).key

        self.factory = APIRequestFactory()

        self.user_with_token.is_active = True
        self.user_with_token.save()

        self.whoami_url = reverse("whoami")  # Suppose that url name is 'whoami'

    def test_authenticated_user_returns_username_and_email(self):
        """
        Test that an authenticated user receives their username and email.
        """
        request = self.factory.get(self.whoami_url)
        force_authenticate(request, user=self.user_with_token, token=self.access_token)
        response = who_am_i(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["user"]["username"], self.user_with_token.username
        )
        self.assertEqual(response.data["user"]["email"], self.user_with_token.email)

    def test_unauthenticated_user_returns_error_message(self):
        """
        Test that an unauthenticated user receives an appropriate error message.

        This test sends a request without an access token and verifies
        that the response includes an error message, and has 401 or 403 status code.
        """
        response = self.client.get(self.whoami_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)

    @override_settings(DEBUG=False, TESTING=False)
    def test_production_mode(self):
        """
        Test the production mode functionality of the who_am_i view.

        This function tests whether the who_am_i view correctly handles requests
        in production mode (DEBUG=False). It verifies that sensitive information
        is not returned and that the appropriate production mode indicators are present.

        The test performs the following steps:
        1. Creates an authenticated request to the whoami endpoint.
        2. Calls the who_am_i view with this request.
        3. Verifies that the response status is 200 OK.
        4. Checks that sensitive information (username, email) is not in the response.
        5. Ensures that debug-related information is not present.
        6. Confirms that production mode indicators are present.
        7. Verifies that the user's theme setting is correctly returned.

        Returns:
            None. Assertions within the method will raise exceptions if any test fails.
        """
        request = self.factory.get(self.whoami_url)
        force_authenticate(request, user=self.user_with_token, token=self.access_token)
        response = who_am_i(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("username", str(response.data))
        self.assertNotIn("email", str(response.data))
        self.assertNotIn("DEBUG", str(response.data))
        self.assertNotIn("fa_2", str(response.data))
        self.assertIn("PRODUCTION", str(response.data))
        self.assertIn("theme", str(response.data))
        self.assertEqual(response.data["user"]["theme"], "light")

    @override_settings(DEBUG=True)
    def test_debug_mode(self):
        """
        Test the debug mode functionality of the who_am_i view.

        This function tests whether the who_am_i view correctly returns debug information
        when in debug mode. It checks for the presence of the authenticated user's username
        and email, as well as the DEBUG and fa_2 flags in the response data.

        The test performs the following steps:
        1. Creates an authenticated request to the whoami endpoint.
        2. Calls the who_am_i view with this request.
        3. Verifies that the response status is 200 OK.
        4. Checks that the returned username and email match the authenticated user's details.
        5. Ensures that the DEBUG and fa_2 flags are present in the response data.

        Returns:
            None. Assertions within the method will raise exceptions if any test fails.
        """
        request = self.factory.get(self.whoami_url)
        force_authenticate(request, user=self.user_with_token, token=self.access_token)
        response = who_am_i(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["user"]["username"], self.user_with_token.username
        )
        self.assertEqual(response.data["user"]["email"], self.user_with_token.email)
        self.assertIn("DEBUG", str(response.data))
        self.assertIn("fa_2", str(response.data))
        self.assertIn("theme", str(response.data))


class NoteTestViewSet(APITestCase):
    """
    These tests are check note viewset is correctly working
    """

    def setUp(self):
        """
        Making headers to login as user
        """
        self.user = User.objects.create(
            username="testuser", email="example@example.com", password="qwerty123"
        )
        self.access_token_user = Token.objects.create(user=self.user).key
        self.header_user = {"Authorization": f"Token {self.access_token_user}"}

        self.another_user = User.objects.create(
            username="anotheruser", email="another@example.com", password="qwerty123"
        )
        self.access_token_another = Token.objects.create(user=self.another_user).key
        self.header_another = {"Authorization": f"Token {self.access_token_another}"}

        self.note_1_by_user_json = {
            "title": "Note 1 by user",
            "description": "desc 1",
            "tags": [],
            "date_of_note": "28/3/2024",
        }
        self.note_1_by_another_user_json = {
            "title": "Note 1 by another user",
            "description": "desc 1",
            "tags": [],
        }
        self.note_2_by_user_json = {
            "title": "Note 2 by user",
            "description": "desc 2",
            "tags": [],
        }
        self.note_3_by_user_json = {
            "title": "Third note by user",
            "description": "Content of note 3",
            "tags": [],
        }
        self.note_4_by_user_json = {
            "title": "Note with title and content",
            "description": "this is content and title",
            "tags": [],
        }

        self.note_with_tag = {
            "title": "Note with tag",
            "description": "Note with tag",
            "tags": [1],
        }
        self.tag = {"title": "Tag 1", "colour": "#FF0000"}

    def test_list(self):
        """Tests if main page returns list of notes"""
        url = reverse("note_default-list")
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_create(self):
        """Tests if correctly create"""
        url = reverse("note_default-list")
        response = self.client.post(
            url, headers=self.header_user, data=self.note_1_by_user_json
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("Note 1", response.data["title"])

        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Note 1", response.data[0]["title"])

    def test_change(self):
        """Tests if changes are correctly working"""
        url1 = reverse("note_default-list")
        url2 = url1 + "1/"
        self.client.post(url1, headers=self.header_user, data=self.note_1_by_user_json)

        response = self.client.patch(
            url2, data={"title": "New title"}, headers=self.header_user
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(url1, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("New title", response.data[0]["title"])

    def test_delete(self):
        """Tests if deleting is working correct"""
        url = reverse("note_default-list")
        self.client.post(url, headers=self.header_user, data=self.note_1_by_user_json)

        response = self.client.delete(url + "1/", headers=self.header_user)

        self.assertEqual(response.status_code, 204)
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_both_users_notes(self):
        """Tests if both users see only own notes"""
        url = reverse("note_default-list")
        # user create
        self.client.post(url, headers=self.header_user, data=self.note_1_by_user_json)
        # another user create
        self.client.post(
            url, headers=self.header_another, data=self.note_1_by_another_user_json
        )

        # user get list of his notes
        response_user = self.client.get(url, headers=self.header_user)
        self.assertEqual(response_user.status_code, 200)
        self.assertEqual(len(response_user.data), 1)
        self.assertIn("Note 1 by user", response_user.data[0]["title"])

        # another user get list of his notes
        response_another = self.client.get(url, headers=self.header_another)
        self.assertEqual(response_another.status_code, 200)
        self.assertEqual(len(response_another.data), 1)
        self.assertIn("Note 1 by another user", response_another.data[0]["title"])

    def test_create_both_users(self):
        """Tests if correctly create for both users"""
        url = reverse("note_default-list")
        # user create
        response_user = self.client.post(
            url, headers=self.header_user, data=self.note_1_by_user_json
        )
        self.assertEqual(response_user.status_code, 201)
        self.assertIn("Note 1 by user", response_user.data["title"])

        # another user create
        response_another = self.client.post(
            url, headers=self.header_another, data=self.note_1_by_another_user_json
        )
        self.assertEqual(response_another.status_code, 201)
        self.assertIn("Note 1 by another user", response_another.data["title"])

    def test_change_both_users(self):
        """Tests if both users can change their own note"""
        url1 = reverse("note_default-list")
        # user create
        self.client.post(url1, headers=self.header_user, data=self.note_1_by_user_json)
        # another user create
        self.client.post(
            url1, headers=self.header_another, data=self.note_1_by_another_user_json
        )

        # user change his note
        response_user = self.client.patch(
            url1 + "1/", data={"title": "New title by user"}, headers=self.header_user
        )
        self.assertEqual(response_user.status_code, 200)
        response_user_get = self.client.get(url1, headers=self.header_user)
        self.assertIn("New title by user", response_user_get.data[0]["title"])

        # another user change his note
        response_another = self.client.patch(
            url1 + "2/",
            data={"title": "New title by another user"},
            headers=self.header_another,
        )
        self.assertEqual(response_another.status_code, 200)
        response_another_get = self.client.get(url1, headers=self.header_another)
        self.assertIn(
            "New title by another user", response_another_get.data[0]["title"]
        )

    def test_delete_both_users(self):
        """Tests if both users can delete own note"""
        url = reverse("note_default-list")
        # user create
        self.client.post(url, headers=self.header_user, data=self.note_1_by_user_json)
        # another user create
        self.client.post(
            url, headers=self.header_another, data=self.note_1_by_another_user_json
        )

        # user delete his note
        response_user_delete = self.client.delete(url + "1/", headers=self.header_user)
        self.assertEqual(response_user_delete.status_code, 204)
        response_user_get = self.client.get(url, headers=self.header_user)
        self.assertEqual(len(response_user_get.data), 0)

        # another user delete his note
        response_another_delete = self.client.delete(
            url + "2/", headers=self.header_another
        )
        self.assertEqual(response_another_delete.status_code, 204)
        response_another_get = self.client.get(url, headers=self.header_another)
        self.assertEqual(len(response_another_get.data), 0)

    def test_user_cannot_change_another_user_note(self):
        """Tests if user cant change another user's note"""
        url = reverse("note_default-list")
        # another user create note
        self.client.post(
            url, headers=self.header_another, data=self.note_1_by_another_user_json
        )
        # user try change another user note
        response = self.client.patch(
            url + "1/", data={"title": "Try to change"}, headers=self.header_user
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_another_user_note(self):
        """Tests if user cant delete another user's note"""
        url = reverse("note_default-list")
        # another user create note
        self.client.post(
            url, headers=self.header_another, data=self.note_1_by_another_user_json
        )
        # user try delete another user note
        response = self.client.delete(url + "1/", headers=self.header_user)
        self.assertEqual(response.status_code, 404)

    def search_test(self):
        """Tests if currently working searching"""
        url = reverse("note_default-list")
        self.client.post(url, headers=self.header_user, data=self.note_1_by_user_json)
        self.client.post(url, headers=self.header_user, data=self.note_2_by_user_json)
        self.client.post(url, headers=self.header_user, data=self.note_3_by_user_json)
        self.client.post(url, headers=self.header_user, data=self.note_4_by_user_json)
        response = self.client.get(
            url + "search/?query=Note 1", headers=self.header_user
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertIn("Note 1", str(response.data))

        response = self.client.get(url + "search/?query=Note", headers=self.header_user)
        self.assertEqual(response.status_code, 200)

        # Because sqlite have a bug with searching by register
        if settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
            self.assertEqual(len(response.data), 2)
        else:
            self.assertEqual(len(response.data), 4)

    def search_by_tag_test(self):
        """Tests if searching by tag working currently"""
        url = reverse("note_default-list")
        self.client.post(url, headers=self.header_user, data=self.note_1_by_user_json)

        self.client.post(reverse("tag-list"), headers=self.header_user, data=self.tag)

        resp = self.client.post(url, headers=self.header_user, data=self.note_with_tag)
        response = self.client.get(
            url + "search-by-tag/?Tag=1", headers=self.header_user
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertIn("Note with tag", str(response.data))

        response = self.client.get(
            url + "search-by-tag/?Tag=2", headers=self.header_user
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)


class TagTestViewSet(APITestCase):
    """
    These tests are check note viewset is correctly working
    """

    def setUp(self):
        """
        Making headers to login as user
        """
        self.user = User.objects.create(
            username="testuser",
            email="example@example.com",
            password="qwerty123",
            theme="light",
        )
        self.access_token_user = Token.objects.create(user=self.user).key
        self.header_user = {"Authorization": f"Token {self.access_token_user}"}

        self.another_user = User.objects.create(
            username="anotheruser", email="another@example.com", password="qwerty123"
        )
        self.access_token_another = Token.objects.create(user=self.another_user).key
        self.header_another = {"Authorization": f"Token {self.access_token_another}"}

        self.tag_1_by_user_json = {"title": "Tag 1 by user", "colour": "#FF0000"}
        self.tag_1_by_another_user_json = {
            "title": "Tag 1 by another user",
            "colour": "#FF0000",
        }

    def test_list(self):
        """Tests if main page returns list of notes"""
        url = reverse("tag-list")
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_create(self):
        """Tests if correctly create"""
        url = reverse("tag-list")
        response = self.client.post(
            url, headers=self.header_user, data=self.tag_1_by_user_json
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("Tag 1", response.data["title"])

        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tag 1", response.data[0]["title"])

    def test_change(self):
        """Tests if changes are correctly working"""
        url1 = reverse("tag-list")
        url2 = url1 + "1/"
        self.client.post(url1, headers=self.header_user, data=self.tag_1_by_user_json)

        response = self.client.patch(
            url2, data={"title": "New title"}, headers=self.header_user
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(url1, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("New title", response.data[0]["title"])

    def test_delete(self):
        """Tests if deleting is working correct"""
        url = reverse("tag-list")
        self.client.post(url, headers=self.header_user, data=self.tag_1_by_user_json)

        response = self.client.delete(url + "1/", headers=self.header_user)

        self.assertEqual(response.status_code, 204)
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_both_users_notes(self):
        """Tests if both users see only own notes"""
        url = reverse("tag-list")
        # user create
        self.client.post(url, headers=self.header_user, data=self.tag_1_by_user_json)
        # another user create
        self.client.post(
            url, headers=self.header_another, data=self.tag_1_by_another_user_json
        )

        # user get list of his notes
        response_user = self.client.get(url, headers=self.header_user)
        self.assertEqual(response_user.status_code, 200)
        self.assertEqual(len(response_user.data), 1)
        self.assertIn("Tag 1 by user", response_user.data[0]["title"])

        # another user get list of his notes
        response_another = self.client.get(url, headers=self.header_another)
        self.assertEqual(response_another.status_code, 200)
        self.assertEqual(len(response_another.data), 1)
        self.assertIn("Tag 1 by another user", response_another.data[0]["title"])

    def test_create_both_users(self):
        """Tests if correctly create for both users"""
        url = reverse("tag-list")
        # user create
        response_user = self.client.post(
            url, headers=self.header_user, data=self.tag_1_by_user_json
        )
        self.assertEqual(response_user.status_code, 201)
        self.assertIn("Tag 1 by user", response_user.data["title"])

        # another user create
        response_another = self.client.post(
            url, headers=self.header_another, data=self.tag_1_by_another_user_json
        )
        self.assertEqual(response_another.status_code, 201)
        self.assertIn("Tag 1 by another user", response_another.data["title"])

    def test_change_both_users(self):
        """Tests if both users can change their own note"""
        url1 = reverse("tag-list")
        # user create
        self.client.post(url1, headers=self.header_user, data=self.tag_1_by_user_json)
        # another user create
        self.client.post(
            url1, headers=self.header_another, data=self.tag_1_by_another_user_json
        )

        # user change his note
        response_user = self.client.patch(
            url1 + "1/", data={"title": "New title by user"}, headers=self.header_user
        )
        self.assertEqual(response_user.status_code, 200)
        response_user_get = self.client.get(url1, headers=self.header_user)
        self.assertIn("New title by user", response_user_get.data[0]["title"])

        # another user change his note
        response_another = self.client.patch(
            url1 + "2/",
            data={"title": "New title by another user"},
            headers=self.header_another,
        )
        self.assertEqual(response_another.status_code, 200)
        response_another_get = self.client.get(url1, headers=self.header_another)
        self.assertIn(
            "New title by another user", response_another_get.data[0]["title"]
        )

    def test_delete_both_users(self):
        """Tests if both users can delete own note"""
        url = reverse("tag-list")
        # user create
        self.client.post(url, headers=self.header_user, data=self.tag_1_by_user_json)
        # another user create
        self.client.post(
            url, headers=self.header_another, data=self.tag_1_by_another_user_json
        )

        # user delete his note
        response_user_delete = self.client.delete(url + "1/", headers=self.header_user)
        self.assertEqual(response_user_delete.status_code, 204)
        response_user_get = self.client.get(url, headers=self.header_user)
        self.assertEqual(len(response_user_get.data), 0)

        # another user delete his note
        response_another_delete = self.client.delete(
            url + "2/", headers=self.header_another
        )
        self.assertEqual(response_another_delete.status_code, 204)
        response_another_get = self.client.get(url, headers=self.header_another)
        self.assertEqual(len(response_another_get.data), 0)

    def test_user_cannot_change_another_user_note(self):
        """Tests if user cant change another user's note"""
        url = reverse("tag-list")
        # another user create note
        self.client.post(
            url, headers=self.header_another, data=self.tag_1_by_another_user_json
        )
        # user try change another user note
        response = self.client.patch(
            url + "1/", data={"title": "Try to change"}, headers=self.header_user
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_another_user_note(self):
        """Tests if user cant delete another user's note"""
        url = reverse("tag-list")
        # another user create note
        self.client.post(
            url, headers=self.header_another, data=self.tag_1_by_another_user_json
        )
        # user try delete another user note
        response = self.client.delete(url + "1/", headers=self.header_user)
        self.assertEqual(response.status_code, 404)


class TestUpdateUserInfo(APITestCase):
    """
    Tests if currently changing fa2_status, telegram id, theme, language, timezone

    """

    def setUp(self):
        self.user_without_telegram_id = User.objects.create_user(
            username="user1",
            email="example1@example.com",
            password="password1",
            theme="light",
            language="en",
        )
        self.user_without_telegram_id.fa_2 = False  # Initialize fa_2
        self.user_without_telegram_id.save()

        self.access_token_user1 = Token.objects.create(
            user=self.user_without_telegram_id
        ).key
        self.header_user1 = {"Authorization": f"Token {self.access_token_user1}"}

        self.user_with_telegram_id = User.objects.create_user(
            username="user2", email="example2@example.com", password="password2"
        )
        self.user_with_telegram_id.telegram_id = "123456"
        self.user_with_telegram_id.fa_2 = False  # Initialize fa_2
        self.user_with_telegram_id.save()

        self.access_token_user2 = Token.objects.create(
            user=self.user_with_telegram_id
        ).key
        self.header_user2 = {"Authorization": f"Token {self.access_token_user2}"}

        self.url = reverse("change-userinfo")

    def test_update_theme(self):
        """Test updating the user's theme preference."""
        data = {"theme": "dark"}
        self.assertEqual(self.user_without_telegram_id.theme, "light")
        response = self.client.patch(self.url, data, headers=self.header_user1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_without_telegram_id.refresh_from_db()
        self.assertEqual(self.user_without_telegram_id.theme, "dark")

        # Test with invalid theme
        data = {"theme": "invalid_theme"}
        response = self.client.patch(self.url, data, headers=self.header_user1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_language(self):
        """Test updating the user's language preference."""
        data = {"language": "ru"}
        self.assertEqual(self.user_without_telegram_id.language, "en")
        response = self.client.patch(self.url, data, headers=self.header_user1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_without_telegram_id.refresh_from_db()
        self.assertEqual(self.user_without_telegram_id.language, "ru")

        # Test with invalid language
        data = {"language": "invalid_lang"}
        response = self.client.patch(self.url, data, headers=self.header_user1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_currently_display_in_whoami(self):
        """
        Just retests whoami
        """
        url = reverse("whoami")

        request = self.client.get(url, headers=self.header_user1)
        self.assertEqual(request.status_code, 200)
        self.assertIsNone(
            request.data["user"].get("telegram_id")
        )  # Use .get() to avoid KeyError
        self.assertFalse(
            request.data["user"].get("fa_2")
        )  # Use .get() to avoid KeyError

        request = self.client.get(url, headers=self.header_user2)
        self.assertEqual(request.status_code, 200)
        self.assertEqual(
            request.data["user"].get("telegram_id"),
            self.user_with_telegram_id.telegram_id,
        )  # Use .get()
        self.assertFalse(request.data["user"].get("fa_2"))  # Use .get()

    def test_changing_telegram_id(self):
        """
        Test if changing telegram_id is currently working
        """
        whoami = reverse("whoami")
        url = self.url
        # Change telegram_id for user1
        data = {"telegram_id": "abcde"}
        request = self.client.patch(
            url, data, headers=self.header_user1, format="json"
        )  # added format='json'
        self.assertEqual(request.status_code, 200)

        # Retrieve updated user info
        request = self.client.get(whoami, headers=self.header_user1)
        self.assertEqual(request.status_code, 200)
        self.assertEqual(request.data["user"]["telegram_id"], "abcde")

        # Fetch user1 from the database to verify the change persisted
        updated_user1 = User.objects.get(username="user1")
        self.assertEqual(updated_user1.telegram_id, "abcde")

        # Change telegram_id to None for user2
        data = {"telegram_id": None}
        request = self.client.patch(
            url, data, headers=self.header_user2, format="json"
        )  # added format='json'
        self.assertEqual(request.status_code, 200)

        # Retrieve updated user info
        request = self.client.get(whoami, headers=self.header_user2)
        self.assertEqual(request.status_code, 200)
        self.assertIsNone(request.data["user"]["telegram_id"])

        # Fetch user2 from the database to verify the change persisted
        updated_user2 = User.objects.get(username="user2")
        self.assertIsNone(updated_user2.telegram_id)

    def test_changing_fa_2(self):
        """
        Test if changing fa_2 is currently working
        """
        whoami = reverse("whoami")
        url = self.url
        # Change fa_2 to True for user1
        data = {"fa_2": True}
        request = self.client.patch(url, data, headers=self.header_user1, format="json")
        self.assertEqual(request.status_code, 200)

        # Retrieve updated user info
        request = self.client.get(whoami, headers=self.header_user1)
        self.assertEqual(request.status_code, 200)
        self.assertTrue(request.data["user"]["fa_2"])

        # Fetch user1 from the database to verify the change persisted
        updated_user1 = User.objects.get(username="user1")
        self.assertTrue(updated_user1.fa_2)

        # Change fa_2 to False for user2
        data = {"fa_2": False}
        request = self.client.patch(url, data, headers=self.header_user2, format="json")
        self.assertEqual(request.status_code, 200)

        # Retrieve updated user info
        request = self.client.get(whoami, headers=self.header_user2)
        self.assertEqual(request.status_code, 200)
        self.assertFalse(request.data["user"]["fa_2"])

        # Fetch user2 from the database to verify the change persisted
        updated_user2 = User.objects.get(username="user2")
        self.assertFalse(updated_user2.fa_2)

    def test_update_user_timezone(self):
        """
        Test updating user's timezone.
        """
        new_timezone = "Europe/Paris"
        response = self.client.patch(
            self.url,
            {"timezone": new_timezone},
            headers=self.header_user1,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_without_telegram_id.refresh_from_db()
        self.assertEqual(self.user_without_telegram_id.timezone, new_timezone)

    def test_get_current_time_after_timezone_update(self):
        """
        Test that get_current_time returns correct time after timezone update.
        """
        new_timezone = "America/New_York"
        self.client.patch(
            self.url,
            {"timezone": new_timezone},
            headers=self.header_user1,
            format="json",
        )
        self.user_without_telegram_id.refresh_from_db()

        user_time = self.user_without_telegram_id.get_current_time()
        expected_time = timezone.now().astimezone(pytz.timezone(new_timezone))

        # Compare times allowing for small difference due to execution time
        self.assertAlmostEqual(user_time, expected_time, delta=timedelta(seconds=1))

    def test_invalid_timezone_update(self):
        """
        Test that updating to an invalid timezone returns an error.
        """
        invalid_timezone = "Invalid/Timezone"
        response = self.client.patch(
            self.url,
            {"timezone": invalid_timezone},
            headers=self.header_user1,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("timezone", response.data)

    def test_timezone_affects_note_creation_time(self):
        """
        Test that user's timezone affects the creation time of a new note.
        """
        new_timezone = "Asia/Tokyo"
        self.client.patch(
            self.url,
            {"timezone": new_timezone},
            headers=self.header_user1,
        )
        self.user_without_telegram_id.refresh_from_db()

        note_data = {"title": "Test Note", "description": "This is a test note."}
        response = self.client.post(
            reverse("note_v2-list"), note_data, headers=self.header_user1
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        note = Note.objects.get(id=response.data["id"])
        note_creation_time = note.date_create.astimezone(pytz.timezone(new_timezone))
        user_current_time = self.user_without_telegram_id.get_current_time()

        # Compare times allowing for small difference due to execution time
        self.assertAlmostEqual(
            note_creation_time, user_current_time, delta=timedelta(seconds=5)
        )

    def test_update_multiple_fields(self):
        """Test updating multiple user fields at once."""
        data = {
            "theme": "dark",
            "language": "ru",
            "telegram_id": "12345",
            "fa_2": True,
        }
        response = self.client.patch(self.url, data, headers=self.header_user1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_without_telegram_id.refresh_from_db()
        self.assertEqual(self.user_without_telegram_id.theme, "dark")
        self.assertEqual(self.user_without_telegram_id.language, "ru")
        self.assertEqual(self.user_without_telegram_id.telegram_id, "12345")
        self.assertTrue(self.user_without_telegram_id.fa_2)


class NoteTestViewSetV2(APITestCase):
    """
    Tests for NoteViewSet API v2 with pagination.
    Verifies pagination behavior for version 2 endpoints.
    """

    def setUp(self):
        self.user = User.objects.create(
            username="testuser",
            email="example@example.com",
            password="qwerty123",
            language="ru",
        )
        self.access_token_user = Token.objects.create(user=self.user).key
        self.header_user = {"Authorization": f"Token {self.access_token_user}"}

        # Create 30 test notes to test pagination
        for i in range(30):
            Note.objects.create(
                user=self.user,
                title=f"Note {i}",
                description=f"Description {i}",
            )

    def test_v2_pagination(self):
        """Verify v2 list endpoint returns paginated results (25 per page)."""
        url = reverse("note_v2-list")
        response = self.client.get(url, headers=self.header_user)

        self.assertEqual(response.status_code, 200)
        # Check pagination keys exist
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("results", response.data)
        # Check page size
        self.assertEqual(len(response.data["results"]), 25)
        # Check total count
        self.assertEqual(response.data["count"], 30)
        # Check next page URL
        self.assertIsNotNone(response.data["next"])

    def test_v1_no_pagination(self):
        """Verify v1 list endpoint doesn't have pagination."""
        url = reverse("note_v1-list")
        response = self.client.get(url, headers=self.header_user)

        self.assertEqual(response.status_code, 200)
        # Results should be a regular list
        self.assertIsInstance(response.data, list)
        # All 30 items should be returned
        self.assertEqual(len(response.data), 30)


class NoteTestViewSetV3(APITestCase):
    """Tsts for NoteViewSet API v3 with achived"""

    def setUp(self):
        self.user = User.objects.create(
            username="testuser", email="example@example.com", password="qwerty123"
        )
        self.access_token_user = Token.objects.create(user=self.user).key
        self.header_user = {"Authorization": f"Token {self.access_token_user}"}

        self.note_1 = Note.objects.create(
            user=self.user,
            title=f"Note 1",
            description=f"Description 1",
        )

        self.note_2 = Note.objects.create(
            user=self.user,
            title=f"Note 2",
            date_of_note=datetime.datetime(2270, 1, 1),
            description=f"Description 2",
        )

        self.note_3 = Note.objects.create(
            user=self.user,
            title=f"Note 3",
            description=f"Description 3",
            date_of_note=datetime.datetime.now(),
            is_archived=True,
        )

        self.note_4 = Note.objects.create(
            user=self.user,
            title=f"Note 4",
            description=f"Description 4",
            date_of_note=datetime.datetime(1970, 1, 1),
            is_archived=True,
        )

        self.note_5 = Note.objects.create(
            user=self.user,
            title=f"Note 5",
            date_of_note=datetime.datetime(2270, 1, 1),
            description=f"Description 5",
            is_archived=True,
        )

    def test_list(self):
        """Tests if listing currently and pagination"""
        url = reverse("note_v3-list")
        response = self.client.get(url, headers=self.header_user)

        self.assertEqual(response.status_code, 200)
        # Check pagination keys exist
        self.assertIn("count", str(response.data))
        self.assertIn("next", str(response.data))
        self.assertIn("results", str(response.data))

        # Checks if only unarchived shows
        self.assertIn("Note 1", str(response.data))
        self.assertIn("Note 2", str(response.data))
        self.assertNotIn("Note 3", str(response.data))
        self.assertNotIn("Note 4", str(response.data))

    def test_archived(self):
        """Tests if archived in current pages are currently displaying"""
        url = reverse("note_v3-list")
        url += "archived/"
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.status_code, 200)
        # Check pagination keys exist
        self.assertIn("count", str(response.data))
        self.assertIn("next", str(response.data))
        self.assertIn("results", str(response.data))

        # Checks if only archived shows
        self.assertNotIn("Note 1", str(response.data))
        self.assertNotIn("Note 2", str(response.data))
        self.assertIn("Note 3", str(response.data))
        self.assertIn("Note 4", str(response.data))

        # Checks if custom params are working
        self.assertIn("total_count_7_days", str(response.data))
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(response.data["total_count_7_days"], 1)

    def test_unarchived_v2(self):
        """Tests if unarchived in not current pages is fetching error"""
        url = reverse("note_v2-list")
        url += "unarchived/"
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 400)

        self.assertIn("This method is only in v3+ versions", str(response.data))


class IconUploadSerializerTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.other_user = User.objects.create_user(
            username="otheruser", password="testpass"
        )

        # Create test tags
        self.user_tag = Tag.objects.create(
            title="User Tag", user=self.user, colour="#FFFFFF"
        )
        self.other_user_tag = Tag.objects.create(
            title="Other User Tag", user=self.other_user, colour="#000000"
        )

        # Request context setup
        self.factory = APIRequestFactory()
        self.request = self.factory.post("/dummy-url/")
        self.request.user = self.user

    def test_valid_serializer(self):
        """Test successful validation and file upload with correct permissions"""
        image_file = generate_test_image()
        data = {
            "icon": image_file,
            "tag_id": str(self.user_tag.id),
        }

        serializer = IconUploadSerializer(data=data, context={"request": self.request})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        # Test file saving logic
        instance = serializer.save()
        self.assertEqual(instance.id, self.user_tag.id)

        # Verify file storage properties
        self.assertTrue(instance.icon.startswith("icons/"))
        filename_part = os.path.splitext(instance.icon)[0].split("/")[-1]
        try:
            uuid.UUID(hex=filename_part)
        except ValueError:
            self.fail("Invalid UUID format in filename")

        self.assertTrue(default_storage.exists(instance.icon))

    def test_delete(self):
        """Tests deleting in serializer"""
        image_file = generate_test_image()
        data = {
            "icon": image_file,
            "tag_id": str(self.user_tag.id),
        }

        serializer = IconUploadSerializer(data=data, context={"request": self.request})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        instance = serializer.save()
        self.assertEqual(instance.id, self.user_tag.id)

        filename_part = os.path.splitext(instance.icon)[0].split("/")[-1]
        path = os.path.splitext(instance.icon)[0]

        try:
            uuid.UUID(hex=filename_part)
        except ValueError:
            self.fail("Invalid UUID format in filename")

        self.assertTrue(default_storage.exists(instance.icon))

        serializer.delete()
        self.assertIsNone(self.user_tag.icon)
        self.assertFalse(os.path.exists(path))

    @override_settings(MEDIA_ROOT="media")
    def test_update(self):
        """Tests if update is correctly working"""
        image_file = generate_test_image()
        new_image_file = generate_test_image(color=(155, 0, 155))
        data = {
            "icon": image_file,
            "tag_id": str(self.user_tag.id),
        }

        new_data = {
            "icon": new_image_file,
            "tag_id": str(self.user_tag.id),
        }

        serializer = IconUploadSerializer(data=data, context={"request": self.request})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        instance = serializer.save()
        path = os.path.splitext(instance.icon)[0]
        with open(f"{settings.MEDIA_ROOT}/{path}.png", "rb") as f:
            chunk1 = f.read(4096)
        old_count = len(os.listdir(f'{settings.MEDIA_ROOT}/{path.split("/")[0]}'))

        serializer = IconUploadSerializer(
            data=new_data, context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid())
        instance = serializer.update_icon()

        self.assertEqual(
            old_count, len(os.listdir(f'{settings.MEDIA_ROOT}/{path.split("/")[0]}'))
        )

        with open(f"{settings.MEDIA_ROOT}/{path}.png", "rb") as f:
            chunk2 = f.read(4096)

        self.assertNotEqual(chunk1, chunk2)

        os.remove(f"{settings.MEDIA_ROOT}/{path}.png")

        self.assertFalse(os.path.exists(f"{settings.MEDIA_ROOT}/{path}.png"))

    def test_nonexistent_tag(self):
        """Test validation fails with non-existent tag ID"""
        data = {
            "icon": generate_test_image(),
            "tag_id": "999999",
        }

        serializer = IconUploadSerializer(data=data, context={"request": self.request})
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)

        self.assertIn("Ur tag id is not correct", str(context.exception.detail))

    def test_unauthorized_tag_access(self):
        """Test validation fails when user doesn't own the tag"""
        image_file = generate_test_image()
        data = {
            "icon": image_file,
            "tag_id": str(self.other_user_tag.id),
        }

        serializer = IconUploadSerializer(data=data, context={"request": self.request})
        with self.assertRaises(DRFValidationError) as context:
            serializer.is_valid(raise_exception=True)

        self.assertIn("tag_id", context.exception.detail)
        self.assertEqual(
            context.exception.detail["tag_id"][0].code, "permission_denied"
        )

    def test_invalid_file_type(self):
        """Test validation fails with non-image file"""
        invalid_file = SimpleUploadedFile(
            "test_file.txt", b"file_content", content_type="text/plain"
        )
        data = {
            "icon": invalid_file,
            "tag_id": str(self.user_tag.id),
        }

        serializer = IconUploadSerializer(data=data, context={"request": self.request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("icon", serializer.errors)
        self.assertEqual(serializer.errors["icon"][0].code, "invalid_image")

    def test_filename_uniqueness(self):
        """Test generated filenames are unique for subsequent uploads"""
        image_file1 = generate_test_image()
        image_file2 = generate_test_image()

        # First upload
        data1 = {
            "icon": image_file1,
            "tag_id": str(self.user_tag.id),
        }
        serializer1 = IconUploadSerializer(
            data=data1, context={"request": self.request}
        )
        serializer1.is_valid(raise_exception=True)
        instance1 = serializer1.save()

        # Second upload
        data2 = {
            "icon": image_file2,
            "tag_id": str(self.user_tag.id),
        }
        serializer2 = IconUploadSerializer(
            data=data2, context={"request": self.request}
        )
        serializer2.is_valid(raise_exception=True)
        instance2 = serializer2.save()

        self.assertNotEqual(instance1.icon, instance2.icon)

    def test_empty_tag_id(self):
        """
        Test that the serializer raises a validation error when 'tag_id' is blank.
        """
        image_file = generate_test_image()
        data = {
            "icon": image_file,
            "tag_id": "",  # blank tag_id should not be allowed
        }
        serializer = IconUploadSerializer(data=data, context={"request": self.request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("tag_id", serializer.errors)
        # The exact error message/code may vary; checking for existence is sufficient.


class IconAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", language="en"
        )
        self.tag = Tag.objects.create(
            title="Test Tag", user=self.user, colour="#FFFFFF"
        )
        self.client.force_authenticate(user=self.user)
        self.image = generate_test_image()

    def test_upload_icon_success(self):
        url = reverse("icon-upload")
        data = {"tag_id": str(self.tag.id), "icon": self.image}

        response = self.client.post(url, data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.tag.refresh_from_db()
        self.assertTrue(bool(self.tag.icon))
        self.assertEqual(response.data["icon"], self.tag.icon)
        # Cleanup uploaded file
        if self.tag.icon:
            default_storage.delete(self.tag.icon)

    def test_upload_icon_invalid_tag(self):
        url = reverse("icon-upload")
        data = {"tag_id": "invalid-uuid", "icon": self.image}

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_icon_success(self):
        # First upload an icon
        self.test_upload_icon_success()

        url = reverse("icon-update")
        new_image = generate_test_image()
        data = {"tag_id": str(self.tag.id), "icon": new_image}

        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_icon_success(self):
        # First upload an icon
        self.test_upload_icon_success()

        url = reverse("icon-delete")
        data = {"tag_id": str(self.tag.id)}

        response = self.client.delete(url, data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.tag.refresh_from_db()
        self.assertFalse(bool(self.tag.icon))

    def test_delete_non_existing_icon(self):
        url = reverse("icon-delete")
        data = {"tag_id": str(self.tag.id)}

        response = self.client.delete(url, data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_unauthorized_access(self):
        self.client.logout()

        urls = [reverse("icon-upload"), reverse("icon-update"), reverse("icon-delete")]

        for url in urls:
            response = self.client.post(url, {})
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutApiTestCase(APITestCase):
    """Tests if logout is working correctly"""

    def setUp(self):
        self.user = User.objects.create(
            username="testuser", email="example@example.com", password="qwerty123"
        )
        self.access_token_user = Token.objects.create(user=self.user).key
        self.header_user = {"Authorization": f"Token {self.access_token_user}"}

    def test_logout_page_with_no_login(self):
        """Tests if logout page is accessible without login."""
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_page_with_login(self):
        """Tests if logout page is accessible with login. Also testing deleting Token"""
        self.assertTrue(Token.objects.all().exists())
        response = self.client.get(reverse("logout"), headers=self.header_user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("logged out", str(response.data))
        self.assertFalse(Token.objects.all().exists())

class GetEmailByUsername(APITestCase):
    """Tests if get_email_by_username view works correctly"""

    def setUp(self):
        self.user_username = "testuser"
        self.user_email = "example@example.com"
        self.user = User.objects.create(
            username=self.user_username, email=self.user_email, password="qwerty123"
        )
        self.url = reverse("get_email_by_username")

    def test_no_data(self):
        """Tests if no data view returns 400"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "No username in request")

    def test_not_correct_username(self):
        """Tests if not correct username returns 400"""
        response = self.client.get(self.url, {"username":"not_correct_username"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "No user with this username")

    def test_correctly_working(self):
        """Tests if correctly working with correct data"""
        response = self.client.get(self.url, {"username":self.user_username})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.user_email)

