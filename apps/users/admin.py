"""Admin configuration for the users app."""
from __future__ import annotations

from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "phone", "role", "created_at")
    search_fields = ("user__username", "user__email", "full_name", "phone")
    list_filter = ("role",)
