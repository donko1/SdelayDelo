from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.timezone import now, timedelta
from django.conf import settings


from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token

from dateutil.relativedelta import relativedelta

import uuid

from .models import Note, Tag, custom_user, TokenToEmail, Notification
from .serializers import TagSerializer, NoteSerializer
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


User = get_user_model()


class UserCustomModelTest(TestCase):
    """This test case tests if user model is custom_user model from ./models.py"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpassword"
        )

    def check_if_user_models_are_the_same(self):
        """Tests if models are the same"""
        self.assertEqual(custom_user, User)

    def test_telegram_id_field(self):
        """Tests if telegram id field is exists and correct working. Checking validators"""
        self.assertEqual(self.user.telegram_id, None)
        self.user.telegram_id = 123
        self.user.save()
        self.assertEqual(123, self.user.telegram_id)
        self.user.telegram_id = "x" * 300  # More than 255 symbols
        with self.assertRaises(DjangoValidationError):
            self.user.full_clean()
            self.user.save()


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
        """Test that a Note can have multiple tags assigned."""
        note = Note.objects.create(
            user=self.user, title="Tagged Note", description="This note is tagged."
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
            user=self.user, title="Test-note-3", description="some description-3"
        )
        note4 = Note.objects.create(
            user=self.user, title="Test-note-4", description="some description-4"
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


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.notification_data = {
            "user": self.user,
            "title": "Test Notification",
            "content": "This is a test notification.",
            "is_repeating": True,
            "repeat_type": "daily",
            "repeat_params": None,
            "is_active": True,
        }

    def create_notification(self, **kwargs):
        data = {**self.notification_data, **kwargs}
        return Notification.objects.create(**data)

    def test_str_representation(self):
        """
        Test the string representation of the Notification model.
        It should return the title and username of the user.
        """
        notification = self.create_notification()
        expected_str = f"{notification.title} - {notification.user.username}"
        self.assertEqual(str(notification), expected_str)

    def test_update_next_notification_daily(self):
        """
        Test the update_next_notification method for daily repeat type.
        The next_notification_date should be incremented by one day.
        """
        notification = self.create_notification(repeat_type="daily")
        initial_next_date = notification.next_notification_date
        notification.update_next_notification()
        self.assertEqual(
            notification.next_notification_date, initial_next_date + timedelta(days=1)
        )

    def test_update_next_notification_weekly(self):
        """
        Test the update_next_notification method for weekly repeat type.
        The next_notification_date should be incremented by one week.
        """
        notification = self.create_notification(repeat_type="weekly")
        initial_next_date = notification.next_notification_date
        notification.update_next_notification()
        self.assertEqual(
            notification.next_notification_date, initial_next_date + timedelta(weeks=1)
        )

    def test_update_next_notification_monthly(self):
        """
        Test the update_next_notification method for monthly repeat type.
        The next_notification_date should be incremented by one month.
        """
        notification = self.create_notification(repeat_type="monthly")
        initial_next_date = notification.next_notification_date
        notification.update_next_notification()
        self.assertEqual(
            notification.next_notification_date,
            initial_next_date + relativedelta(months=1),
        )

    def test_update_next_notification_yearly(self):
        """
        Test the update_next_notification method for yearly repeat type.
        The next_notification_date should be incremented by one year.
        """
        notification = self.create_notification(repeat_type="yearly")
        initial_next_date = notification.next_notification_date
        notification.update_next_notification()
        self.assertEqual(
            notification.next_notification_date,
            initial_next_date + relativedelta(years=1),
        )

    def test_non_repeating_notification_deactivation(self):
        """
        Test that a non-repeating notification gets deactivated after sending.
        """
        notification = self.create_notification(is_repeating=False)
        notification.send_notification()
        self.assertFalse(notification.is_active)


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
        with self.assertRaises(ValidationError) as context:
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
        with self.assertRaises(ValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn("This field is required.", str(context.exception))

        data_without_description = {
            "title": "Note without description",
            "tags": [self.tag.id],
        }
        serializer = NoteSerializer(
            context=self.get_serializer_context(), data=data_without_description
        )
        with self.assertRaises(ValidationError) as context:
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
        with self.assertRaises(ValidationError) as context:
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
        with self.assertRaises(ValidationError) as context:
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
        with self.assertRaises(ValidationError) as context:
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
        with self.assertRaises(ValidationError) as context:
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
        self.assertTrue(TokenToEmail.objects.filter(email="test@example.com").exists())

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
        response = self.client.post(url, {"username": "testuser", "password": password})
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
            username="testuser", password=hashed_password, email="example@example.com"
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
        token_obj = TokenToEmail.objects.create(
            email="test@example.com", is_verified=True
        )

        password = "qwerty123"
        hashed_password = make_password(password)

        User.objects.create(
            email="test@example.com",
            username="testuser",
            password=hashed_password,
            fa_2=True,
        )
        raw_token = str(uuid.uuid4())
        token_obj.token_hash = TokenToEmail.hash_token(raw_token)
        token_obj.save()

        response = self.client.post(
            url,
            {"email": "test@example.com", "password": password},
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn(
            f"Now visit {url_check_code} to continue", response.data["detail"]
        )
        self.assertEqual(f"t**t@example.com", response.data["email"])

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
        url = reverse("note-list")
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_create(self):
        """Tests if correctly create"""
        url = reverse("note-list")
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
        url1 = reverse("note-list")
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
        url = reverse("note-list")
        self.client.post(url, headers=self.header_user, data=self.note_1_by_user_json)

        response = self.client.delete(url + "1/", headers=self.header_user)

        self.assertEqual(response.status_code, 204)
        response = self.client.get(url, headers=self.header_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_both_users_notes(self):
        """Tests if both users see only own notes"""
        url = reverse("note-list")
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
        url = reverse("note-list")
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
        url1 = reverse("note-list")
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
        url = reverse("note-list")
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
        url = reverse("note-list")
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
        url = reverse("note-list")
        # another user create note
        self.client.post(
            url, headers=self.header_another, data=self.note_1_by_another_user_json
        )
        # user try delete another user note
        response = self.client.delete(url + "1/", headers=self.header_user)
        self.assertEqual(response.status_code, 404)

    def search_test(self):
        """Tests if currently working searching"""
        url = reverse("note-list")
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
        url = reverse("note-list")
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
            username="testuser", email="example@example.com", password="qwerty123"
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
    Tests if currently changing fa2_status, telegram id, etc.
    """

    def setUp(self):
        self.user_without_telegram_id = (
            User.objects.create_user(  # Use create_user for passwords
                username="user1", email="example1@example.com", password="password1"
            )
        )
        self.user_without_telegram_id.fa_2 = False  # Initialize fa_2
        self.user_without_telegram_id.save()

        self.access_token_user1 = Token.objects.create(
            user=self.user_without_telegram_id
        ).key
        self.header_user1 = {"Authorization": f"Token {self.access_token_user1}"}

        self.user_with_telegram_id = (
            User.objects.create_user(  # Use create_user for passwords
                username="user2", email="example2@example.com", password="password2"
            )
        )
        self.user_with_telegram_id.telegram_id = "123456"
        self.user_with_telegram_id.fa_2 = False  # Initialize fa_2
        self.user_with_telegram_id.save()

        self.access_token_user2 = Token.objects.create(
            user=self.user_with_telegram_id
        ).key
        self.header_user2 = {"Authorization": f"Token {self.access_token_user2}"}

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
        url = reverse("change-userinfo")

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
        url = reverse("change-userinfo")

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
