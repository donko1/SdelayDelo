from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Note, Tag

User = get_user_model()


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
