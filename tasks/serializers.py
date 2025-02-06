from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.storage import default_storage

import uuid
import os


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


class IconUploadSerializer(serializers.Serializer):
    """Serializer to upload and manage tag icons"""

    icon = serializers.ImageField(required=False, allow_null=False)
    tag_id = serializers.CharField(required=True, allow_null=False, allow_blank=False)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    def validate(self, attrs):
        """Validate that user and tag are the same and correct"""
        attrs = super().validate(attrs)
        user = attrs["user"]
        tag_id = attrs["tag_id"]

        try:
            tag = Tag.objects.get(id=tag_id)
        except (Tag.DoesNotExist, ValueError):
            raise serializers.ValidationError({"detail": "Ur tag id is not correct"})

        if tag.user != user:
            raise serializers.ValidationError(
                {"tag_id": "U dont have rights to change it"}, code="permission_denied"
            )

        attrs["tag"] = tag
        return attrs

    def save(self):
        """Save new icon in media root and update tag's icon path"""
        icon = self.validated_data["icon"]
        tag = self.validated_data["tag"]

        # Generate new unique filename
        file_ext = os.path.splitext(icon.name)[1]
        file_name = f"{uuid.uuid4().hex}{file_ext}"
        file_path = default_storage.save(
            f"{settings.ICON_MEDIA_PATH}/{file_name}", icon
        )

        # Update tag with new icon path

        tag.icon = file_path
        tag.save()

        return tag

    def delete(self):
        """
        Deletes the associated icon file from storage and clears the tag's icon field.
        If the tag does not have an existing icon, no action is taken.
        """
        tag = self.validated_data.get("tag")
        if not tag.icon:
            return

        file_path = tag.icon

        # Delete physical file
        if default_storage.exists(file_path):
            default_storage.delete(file_path)

        # Clear icon path in database
        tag.icon = None
        tag.save()

    def update_icon(self):
        """
        Updates the existing icon file at the current path with the new image.
        The tag's icon field remains unchanged.
        Raises ValidationError if no existing icon is present.
        """
        tag = self.validated_data.get("tag")
        if not tag.icon:
            raise serializers.ValidationError(
                {"icon": "Tag does not have an existing icon to update."}
            )

        icon = self.validated_data["icon"]
        file_path = tag.icon

        # Remove existing file before saving new one to prevent name conflicts
        if default_storage.exists(file_path):
            default_storage.delete(file_path)

        # Save new content to existing path
        default_storage.save(file_path, icon)

        # Persist any potential changes to tag (though icon path remains same)
        tag.save()
        return tag
