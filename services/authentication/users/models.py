"""User app models."""
from __future__ import annotations

import hashlib

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
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
    phone = models.CharField(max_length=20, unique=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["owner", "name"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Property(name={self.name}, owner={self.owner_id})"


def _dorm_cover_upload_path(instance: "Dorm", filename: str) -> str:
    """Return a deterministic upload path for dorm cover images."""

    owner_id = instance.property.owner_id if instance.property_id else "unassigned"
    return f"dorms/{owner_id}/covers/{filename}"


def _dorm_gallery_upload_path(instance: "DormImage", filename: str) -> str:
    """Return upload path for dorm gallery images."""

    owner_id = instance.dorm.property.owner_id if instance.dorm.property_id else "unassigned"
    return f"dorms/{owner_id}/gallery/{filename}"


def _room_gallery_upload_path(instance: "DormRoomImage", filename: str) -> str:
    """Return upload path for room gallery images."""

    owner_id = instance.room.dorm.property.owner_id if instance.room.dorm.property_id else "unassigned"
    return f"dorms/{owner_id}/rooms/{instance.room_id or 'unassigned'}/{filename}"


class Dorm(models.Model):
    """A dormitory offered by a property owner."""

    property = models.ForeignKey(
        Property,
        related_name="dorms",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to=_dorm_cover_upload_path, blank=True, null=True)
    amenities = models.JSONField(default=list, blank=True)
    room_service_available = models.BooleanField(default=False)
    electricity_included = models.BooleanField(default=True)
    water_included = models.BooleanField(default=True)
    internet_included = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["property", "name"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Dorm(name={self.name}, property={self.property_id})"


class DormImage(models.Model):
    """Gallery images for a dorm."""

    dorm = models.ForeignKey(
        Dorm,
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to=_dorm_gallery_upload_path)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"DormImage(dorm={self.dorm_id}, id={self.id})"


class DormRoom(models.Model):
    """A room configuration inside a dorm."""

    class RoomType(models.TextChoices):
        SINGLE = "SINGLE", "Single"
        DOUBLE = "DOUBLE", "Double"
        TRIPLE = "TRIPLE", "Triple"
        QUAD = "QUAD", "Quad"
        STUDIO = "STUDIO", "Studio"
        OTHER = "OTHER", "Other"

    dorm = models.ForeignKey(
        Dorm,
        related_name="rooms",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    room_type = models.CharField(max_length=20, choices=RoomType.choices)
    capacity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2)
    amenities = models.JSONField(default=list, blank=True)
    total_units = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    available_units = models.PositiveIntegerField(default=1)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["dorm", "room_type"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"DormRoom(name={self.name}, dorm={self.dorm_id})"


class DormRoomImage(models.Model):
    """Gallery images for specific dorm rooms."""

    room = models.ForeignKey(
        DormRoom,
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to=_room_gallery_upload_path)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"DormRoomImage(room={self.room_id}, id={self.id})"


class BookingRequest(models.Model):
    """A booking request submitted for a dorm room."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DECLINED = "DECLINED", "Declined"
        CANCELLED = "CANCELLED", "Cancelled"

    room = models.ForeignKey(
        DormRoom,
        related_name="booking_requests",
        on_delete=models.CASCADE,
    )
    seeker_name = models.CharField(max_length=255)
    seeker_email = models.EmailField()
    seeker_phone = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    move_in_date = models.DateField(null=True, blank=True)
    move_out_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    owner_note = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "status"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"BookingRequest(room={self.room_id}, status={self.status})"