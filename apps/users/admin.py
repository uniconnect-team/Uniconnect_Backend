"""Admin configuration for the users app."""
from __future__ import annotations

from django.contrib import admin

from .models import (
    BookingRequest,
    Dorm,
    DormImage,
    DormRoom,
    DormRoomImage,
    Profile,
    Property,
    RoommateRequest,
    UniversityDomain,
    RoommateProfile,
    RoommateMatch,
)


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


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "location", "created_at")
    search_fields = ("name", "location", "owner__user__username")
    autocomplete_fields = ("owner",)


@admin.register(Dorm)
class DormAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "property",
        "is_active",
        "room_service_available",
        "electricity_included",
        "created_at",
    )
    search_fields = ("name", "property__name")
    list_filter = ("is_active", "room_service_available", "electricity_included")
    autocomplete_fields = ("property",)


@admin.register(DormRoom)
class DormRoomAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "dorm",
        "room_type",
        "price_per_month",
        "available_units",
        "is_available",
    )
    list_filter = ("room_type", "is_available")
    search_fields = ("name", "dorm__name")
    autocomplete_fields = ("dorm",)


@admin.register(DormImage)
class DormImageAdmin(admin.ModelAdmin):
    list_display = ("id", "dorm", "caption", "created_at")
    search_fields = ("dorm__name", "caption")
    autocomplete_fields = ("dorm",)


@admin.register(DormRoomImage)
class DormRoomImageAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "caption", "created_at")
    search_fields = ("room__name", "caption")
    autocomplete_fields = ("room",)


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room",
        "seeker_name",
        "status",
        "move_in_date",
        "move_out_date",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("seeker_name", "seeker_email", "room__name")
    autocomplete_fields = ("room",)


@admin.register(RoommateProfile)
class RoommateProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "profile",
        "sleep_schedule",
        "cleanliness_level",
        "social_preference",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "sleep_schedule", "cleanliness_level", "social_preference")
    search_fields = ("profile__user__username", "profile__full_name", "interests", "bio")
    autocomplete_fields = ("profile",)


@admin.register(RoommateMatch)
class RoommateMatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "seeker",
        "match",
        "compatibility_score",
        "is_viewed",
        "is_favorited",
        "created_at",
    )
    list_filter = ("is_viewed", "is_favorited")
    search_fields = ("seeker__user__username", "match__user__username")
    autocomplete_fields = ("seeker", "match")


@admin.register(RoommateRequest)
class RoommateRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sender",
        "receiver",
        "status",
        "created_at",
        "responded_at",
    )
    list_filter = ("status",)
    search_fields = ("sender__user__username", "receiver__user__username", "message")
    autocomplete_fields = ("sender", "receiver")
