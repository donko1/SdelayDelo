# serializers.py
from rest_framework import serializers
from .models import Tag, Note


class TagSerializer(serializers.ModelSerializer):
    """
    Serializer for the Tag model.
    Fields:
    - id: Primary key of the tag.
    - title: Name of the tag.
    - user: Owner of the tag.
    - colour: Hexadecimal color code associated with the tag.
    - icon: Optional icon for the tag.
    """

    class Meta:
        model = Tag
        fields = ["id", "title", "user", "colour", "icon"]


class NoteSerializer(serializers.ModelSerializer):
    """
    Serializer for the Note model.
    Fields:
    - id: Primary key of the note.
    - user: Owner of the note.
    - title: Title of the note.
    - description: Content of the note.
    - date_create: Timestamp when the note was created.
    - date_changed: Timestamp when the note was last modified.
    - tags: Associated tags, serialized as read-only nested objects.
    """

    tags = TagSerializer(many=True, read_only=True)  # Nested serializer for tags

    class Meta:
        model = Note
        fields = [
            "id",
            "user",
            "title",
            "description",
            "date_create",
            "date_changed",
            "tags",
        ]
