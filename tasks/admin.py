from django.contrib import admin

from .models import Tag, Note, custom_user, TokenToEmail


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin interface for Tag model."""

    list_display = ("title", "user", "colour", "icon")
    search_fields = ("title", "user__username")
    list_filter = ("user",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Admin interface for Note model."""

    list_display = ("title", "user", "date_create", "date_changed", "is_archived")
    search_fields = ("title", "description", "user__username")
    list_filter = ("user", "tags")
    filter_horizontal = ("tags",)


@admin.register(custom_user)
class UserAdmin(admin.ModelAdmin):
    """Admin interface for User model."""

    list_display = ("username", "email", "telegram_id")
    search_fields = ("username", "email", "telegram_id")


@admin.register(TokenToEmail)
class TokenToEmailAdmin(admin.ModelAdmin):
    """Admin interface for TokenToEmail model"""

    list_display = ["email", "code", "token_hash", "is_verified"]
