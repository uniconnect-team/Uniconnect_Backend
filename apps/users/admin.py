"""Admin configuration for the users app."""
from __future__ import annotations

from django.contrib import admin

from .models import (
    Profile,
    Property,
    PropertyImage,
    Room,
    RoomImage,
    UniversityDomain,
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


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "location",
        "electricity_included",
        "cleaning_included",
        "created_at",
    )
    search_fields = ("name", "location", "owner__user__username")
    list_filter = ("electricity_included", "cleaning_included")
    inlines = [PropertyImageInline, RoomInline]


class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 0


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "property",
        "room_type",
        "price_per_month",
        "available_quantity",
        "is_active",
    )
    list_filter = ("room_type", "is_active")
    search_fields = ("name", "property__name")
    inlines = [RoomImageInline]


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ("id", "property", "uploaded_at")
    search_fields = ("property__name",)


@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "uploaded_at")
    search_fields = ("room__name",)
