"""Admin configuration for the users app."""
from __future__ import annotations

from django.contrib import admin

from .models import EmailOTP, PendingRegistration, Profile, UniversityDomain


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "full_name",
        "phone",
        "role",
        "is_student_verified",
        "created_at",
    )
    search_fields = ("user__username", "user__email", "full_name", "phone")
    list_filter = ("role", "is_student_verified")


@admin.register(UniversityDomain)
class UniversityDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "university_name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("domain", "university_name")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("email", "expires_at", "used_at", "attempts", "created_at")
    search_fields = ("email",)
    list_filter = ("used_at",)


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "phone",
        "role",
        "created_at",
        "updated_at",
    )
    search_fields = ("email", "phone")
    list_filter = ("role",)
