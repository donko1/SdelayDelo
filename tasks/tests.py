from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.timezone import now, timedelta
from django.conf import settings


from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token


import uuid

from .models import Note, Tag, custom_user, TokenToEmail
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


class TagSerializerTestCase(APITestCase):
    """
    Test case for the TagSerializer.

    This class contains tests for validating and ensuring the correctness of
    the TagSerializer.
    """

    def setUp(self):
        """
        Set up test data for the TagSerializer tests.

        Creates a user instance and initializes valid and invalid tag data.
        """
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.valid_tag_data = {
            "title": "Test Tag",
            "colour": "#FFFFFF",
            "icon": "icon.png",
            "user": self.user.id,
        }
        self.invalid_tag_data = {
            "title": "Test Tag",
            "colour": "InvalidColor",
        }

    def test_valid_tag_serializer(self):
        """
        Test case for a valid tag serializer.

        Ensures that the serializer successfully validates data and the
        validated data matches the input.
        """
        serializer = TagSerializer(data=self.valid_tag_data)
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
        serializer = TagSerializer(data=self.invalid_tag_data)
        self.assertFalse(serializer.is_valid())

    def test_tag_serializer_missing_fields(self):
        """
        Test case for a tag serializer with missing fields.

        Ensures that the serializer raises ValidationError when required
        fields are missing.
        """
        incomplete_data = {"title": "Incomplete Tag"}
        serializer = TagSerializer(data=incomplete_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("colour", serializer.errors)

    def test_valid_hex_color(self):
        """
        The serializer should accept a valid HEX color.
        """
        data = {"title": "Test Tag", "colour": "#123ABC", "user": self.user.id}
        serializer = TagSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_hex_color(self):
        """
        The serializer should reject an invalid HEX color.
        """
        data = {"title": "Test Tag", "colour": "123ABC", "user": self.user.id}
        serializer = TagSerializer(data=data)
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
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.tag = Tag.objects.create(
            title="Test Tag", colour="#FF5733", user=self.user
        )
        self.valid_note_data = {
            "title": "Test Note",
            "description": "This is a test note.",
            "tags": [self.tag.id],
            "user": self.user.id,
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

    def test_valid_note_serializer(self):
        """
        Test case for a valid note serializer.

        Ensures that the serializer successfully validates data and the
        validated data matches the input.
        """
        serializer = NoteSerializer(data=self.valid_note_data)
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
        serializer = NoteSerializer(data=self.invalid_note_data)
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
        serializer = NoteSerializer(instance=self.note, data=updated_data, partial=True)
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
            "user": self.user.id,
        }
        serializer = NoteSerializer(data=data_with_tags)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        self.assertEqual(validated_data["title"], data_with_tags["title"])
        self.assertEqual(validated_data["description"], data_with_tags["description"])
        self.assertIn(self.tag.id, [tag.id for tag in validated_data["tags"]])

    def test_note_serializer_missing_title(self):
        """
        Test case for a note serializer with a missing title field.

        Ensures that the serializer raises a ValidationError for
        missing required fields.
        """
        data_missing_title = {"description": "No title provided."}
        serializer = NoteSerializer(data=data_missing_title)
        self.assertFalse(serializer.is_valid())
        self.assertIn("title", serializer.errors)


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
        self.assertEqual(
            User.objects.filter(username="testuser")[0].password, "testnewpassworD123"
        )

    def test_login(self):
        """
        Test login with login view
        """
        url = reverse("login")
        user = User.objects.create(username="testuser", password="testpassword123")

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
            url, {"username": "testuser", "password": "testpassword123"}
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
