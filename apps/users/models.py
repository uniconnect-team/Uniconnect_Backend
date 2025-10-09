"""User app models."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


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

    def __str__(self) -> str:
        return f"Profile({self.user.username})"
