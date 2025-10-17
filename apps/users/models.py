"""User app models."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

DEFAULT_VERIFY_TOKEN_TTL_MIN = getattr(settings, "VERIFY_TOKEN_TTL_MIN", 15)


class Profile(models.Model):
    """Stores additional information for a Django user."""

    class Roles(models.TextChoices):
        SEEKER = "SEEKER", "SEEKER"
        OWNER = "OWNER", "OWNER"

    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=10, choices=Roles.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    is_student_verified = models.BooleanField(default=False)
    university_domain = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"Profile({self.user.username})"


class UniversityDomainQuerySet(models.QuerySet["UniversityDomain"]):
    """Custom queryset for active domain lookups."""

    def active(self) -> "UniversityDomainQuerySet":
        return self.filter(is_active=True)


class UniversityDomain(models.Model):
    """Represents an allow-listed university email domain."""

    domain = models.CharField(max_length=255, unique=True)
    university_name = models.CharField(max_length=255)
    country_code = models.CharField(max_length=10, default="LB")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UniversityDomainQuerySet.as_manager()

    class Meta:
        ordering = ["domain"]

    def __str__(self) -> str:
        return f"{self.university_name} ({self.domain})"


class VerificationTokenQuerySet(models.QuerySet["VerificationToken"]):
    """Query helpers for verification tokens."""

    def active(self) -> "VerificationTokenQuerySet":
        now = timezone.now()
        return self.filter(consumed_at__isnull=True, expires_at__gt=now)

    def for_user(self, user: User) -> "VerificationTokenQuerySet":
        return self.filter(user=user)


class VerificationToken(models.Model):
    """Stores hashed verification tokens for student email validation."""

    class Types(models.TextChoices):
        LINK = "link", "Link"
        OTP = "otp", "One-Time Password"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    token_type = models.CharField(max_length=8, choices=Types.choices, default=Types.LINK)
    email = models.EmailField()
    university_domain = models.CharField(max_length=255, blank=True)
    otp_code_hash = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_ip = models.GenericIPAddressField(null=True, blank=True)
    created_ua = models.CharField(max_length=512, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    objects = VerificationTokenQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        status = "consumed" if self.consumed_at else "active"
        return f"VerificationToken(user={self.user_id}, status={status})"

    @classmethod
    def build_hash(cls, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def create_for_user(
        cls,
        user: User,
        *,
        token: str,
        token_type: str = Types.LINK,
        email: str,
        university_domain: str = "",
        expires_at: datetime | None = None,
        created_ip: str | None = None,
        created_ua: str = "",
    ) -> "VerificationToken":
        if expires_at is None:
            expires_at = timezone.now() + timedelta(minutes=DEFAULT_VERIFY_TOKEN_TTL_MIN)

        token_hash = cls.build_hash(token)

        return cls.objects.create(
            user=user,
            token_hash=token_hash,
            token_type=token_type,
            email=email,
            university_domain=university_domain,
            expires_at=expires_at,
            created_ip=created_ip,
            created_ua=created_ua[:512],
        )

    def mark_consumed(self) -> None:
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at"])

    def mark_failed_attempt(self) -> None:
        if self.is_locked:
            return
        now = timezone.now()
        self.failed_attempts += 1
        updates = ["failed_attempts"]
        if self.failed_attempts >= getattr(settings, "VERIFY_MAX_ATTEMPTS", 10):
            self.locked_until = now + timedelta(minutes=getattr(settings, "VERIFY_LOCKOUT_MIN", 30))
            updates.append("locked_until")
        self.save(update_fields=updates)

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())
