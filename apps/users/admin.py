"""Admin configuration for the users app."""
from __future__ import annotations

from django.contrib import admin

from .models import Profile, UniversityDomain, VerificationToken


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "phone", "role", "created_at")
    search_fields = ("user__username", "user__email", "full_name", "phone")
    list_filter = ("role",)


@admin.register(UniversityDomain)
class UniversityDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "university_name", "country_code", "is_active", "updated_at")
    list_filter = ("country_code", "is_active")
    search_fields = ("domain", "university_name")


@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "token_type", "expires_at", "consumed_at")
    list_filter = ("token_type", "consumed_at")
    search_fields = ("user__email", "email")
    readonly_fields = ("token_hash", "created_at", "expires_at", "consumed_at")
