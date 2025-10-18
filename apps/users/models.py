"""User app models."""
from __future__ import annotations

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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Profile({self.user.username})"


class EmailVerificationToken(models.Model):
    """Stores one-time passwords for verifying university emails."""

    class Methods(models.TextChoices):
        OTP = "otp", "OTP"

    user = models.ForeignKey(User, related_name="email_tokens", on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=255)
    otp_hash = models.CharField(max_length=255, null=True, blank=True)
    method = models.CharField(max_length=20, choices=Methods.choices, default=Methods.OTP)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    resend_count = models.PositiveIntegerField(default=0)
    created_ip = models.GenericIPAddressField(null=True, blank=True)
    created_ua = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at
