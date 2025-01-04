from django.contrib import admin

from .models import Tag, Note


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin interface for Tag model."""

    list_display = ("title", "user", "colour", "icon")
    search_fields = ("title", "user__username")
    list_filter = ("user",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Admin interface for Note model."""

    list_display = ("title", "user", "date_create", "date_changed")
    search_fields = ("title", "description", "user__username")
    list_filter = ("user", "tags")
    filter_horizontal = ("tags",)
