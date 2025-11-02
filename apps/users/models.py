"""User app models."""
from __future__ import annotations

import hashlib

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UniversityDomain(models.Model):
    """Allow-listed university email domains."""

    domain = models.CharField(max_length=255, unique=True)
    university_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]
        indexes = [models.Index(fields=["domain"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.domain


class Profile(models.Model):
    """Stores additional information for a Django user."""

    class Roles(models.TextChoices):
        SEEKER = "SEEKER", "SEEKER"
        OWNER = "OWNER", "OWNER"

    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    role = models.CharField(max_length=10, choices=Roles.choices)
    is_student_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    university_domain = models.ForeignKey(
        UniversityDomain,
        related_name="profiles",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)  # NEW FIELD
    profile_completed = models.BooleanField(default=False)  # NEW FIELD
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Profile({self.user.username})"


class EmailOTP(models.Model):
    """Stores email verification one-time passwords."""

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"EmailOTP(email={self.email}, created_at={self.created_at})"

    def is_expired(self) -> bool:
        """Return ``True`` when the OTP can no longer be used."""

        if self.expires_at <= timezone.now():
            return True
        if self.used_at is not None:
            return True
        return False

    def verify(self, code: str) -> bool:
        """Check whether ``code`` matches the stored hash."""

        return hashlib.sha256(code.encode("utf-8")).hexdigest() == self.code_hash


class PendingRegistration(models.Model):
    """Persist pending registration attempts awaiting verification."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    password_hash = models.CharField(max_length=128)
    role = models.CharField(max_length=10, choices=Profile.Roles.choices)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    university_domain = models.ForeignKey(
        UniversityDomain,
        related_name="pending_registrations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"PendingRegistration({self.email})"


class Property(models.Model):
    """Housing property owned by a registered dorm owner."""

    owner = models.ForeignKey(
        Profile,
        related_name="properties",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_image = models.FileField(
        upload_to="property_covers/",
        null=True,
        blank=True,
    )
    amenities = models.JSONField(default=list, blank=True)
    electricity_included = models.BooleanField(default=False)
    cleaning_included = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner", "name"]),
            models.Index(fields=["owner", "created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Property(name={self.name}, owner={self.owner_id})"


class PropertyImage(models.Model):
    """Additional gallery images for a property."""

    property = models.ForeignKey(
        Property,
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.FileField(upload_to="property_images/")
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [models.Index(fields=["property", "uploaded_at"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"PropertyImage(property={self.property_id}, id={self.id})"


class Room(models.Model):
    """Room types and availability within a property."""

    class RoomType(models.TextChoices):
        SINGLE = "SINGLE", "Single"
        DOUBLE = "DOUBLE", "Double"
        SUITE = "SUITE", "Suite"
        OTHER = "OTHER", "Other"

    property = models.ForeignKey(
        Property,
        related_name="rooms",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    room_type = models.CharField(max_length=10, choices=RoomType.choices)
    description = models.TextField(blank=True)
    price_per_month = models.DecimalField(max_digits=8, decimal_places=2)
    capacity = models.PositiveIntegerField(default=1)
    available_quantity = models.PositiveIntegerField(default=0)
    amenities = models.JSONField(default=list, blank=True)
    electricity_included = models.BooleanField(default=False)
    cleaning_included = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["property", "name"]),
            models.Index(fields=["property", "room_type"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Room(name={self.name}, property={self.property_id})"


class RoomImage(models.Model):
    """Gallery images for individual rooms."""

    room = models.ForeignKey(
        Room,
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.FileField(upload_to="room_images/")
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [models.Index(fields=["room", "uploaded_at"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"RoomImage(room={self.room_id}, id={self.id})"