from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.conf import settings

from rest_framework import serializers

from .models import Tag, Note
from .validators import is_hex_color

User = get_user_model()


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

    # if not settings.TESTING:
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    date_of_note = serializers.DateField(
        format="%d/%m/%Y", input_formats=["%d/%m/%Y", "%Y-%m-%d"], required=False
    )

    class Meta:
        model = Note
        fields = [
            "id",
            "title",
            "description",
            "date_create",
            "date_changed",
            "date_of_note",
            "tags",
            "user",
        ]
        read_only_field = ["date_create", "date_changed"]


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration. Handles validation and user creation.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_email(self, value):
        """
        Validates that the email provided is not already in use.
        """
        if User.objects.filter(email=value).exists():
            raise ValidationError("This email is already registered.")
        return value

    def create(self, validated_data):
        """
        Creates a new user instance and returns it.
        """
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user


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

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

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


class UserUpdateSerializer(
    serializers.Serializer
):  # Use Serializer, not ModelSerializer
    """
    Serializer used in change-userinfo to change user info
    """

    telegram_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    fa_2 = serializers.BooleanField(
        required=False, allow_null=True
    )  # Adjust Field based on data type

    def update(self, instance, validated_data: dict):
        """
        Update and return an existing `User` instance, given the validated data.
        """
        instance.telegram_id = validated_data.get(
            "telegram_id", instance.telegram_id
        )  # Use instance value if not provided
        instance.fa_2 = validated_data.get(
            "fa_2", instance.fa_2
        )  # Use instance value if not provided
        instance.save()
        return instance
