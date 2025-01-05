from rest_framework import serializers
from .models import Tag, Note
from django.utils.timezone import now
from .validators import is_hex_color


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
        read_only_field = ["id", "user"]

    def validate_colour(self, value: str) -> str:
        """
        Validates if the provided colour value is a valid HEX color.

        Args:
            value (str): The color code to validate.

        Returns:
            str: The validated color code.

        Raises:
            serializers.ValidationError: If the color code is not valid.
        """
        if not is_hex_color(value):
            raise serializers.ValidationError("Invalid HEX color code.")
        return value


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

    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all())

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
        read_only_field = ["user", "date_create"]
