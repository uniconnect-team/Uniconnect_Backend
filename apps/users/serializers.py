"""Serializers for the users app."""
from __future__ import annotations

import random
import re
from datetime import timedelta
from typing import Any, Dict

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile


def _build_user_payload(user: User) -> Dict[str, Any]:
    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": getattr(profile, "full_name", ""),
        "phone": getattr(profile, "phone", ""),
        "role": getattr(profile, "role", ""),
    }


class ConflictError(APIException):
    """HTTP 409 conflict error."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = _("A user with this email already exists.")
    default_code = "conflict"


class RegisterSerializer(serializers.Serializer):
    """Serializer for registering a new user."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=Profile.Roles.choices)

    def validate_password(self, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise serializers.ValidationError(
                _("Password must contain at least one letter and one digit."),
                code="invalid_password",
            )
        return value

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise ConflictError(_("A user with this email already exists."))
        return value

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        full_name: str = validated_data.get("full_name", "")
        phone: str = validated_data["phone"]
        email: str = validated_data["email"]
        password: str = validated_data["password"]
        role: str = validated_data["role"]

        username_base = email.split("@")[0]
        username_candidate = username_base
        while User.objects.filter(username=username_candidate).exists():
            username_candidate = f"{username_base}{random.randint(1000, 9999)}"

        try:
            with transaction.atomic():
                user = User(username=username_candidate, email=email)
                user.set_password(password)
                user.save()
                Profile.objects.create(
                    user=user,
                    full_name=full_name,
                    phone=phone,
                    role=role,
                )
        except IntegrityError as exc:
            raise serializers.ValidationError({"phone": [_("Phone number must be unique.")]}) from exc

        return _build_user_payload(user)


class LoginSerializer(serializers.Serializer):
    """Serializer handling email/phone login."""

    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        identifier = attrs.get("identifier", "")
        password = attrs.get("password", "")
        remember_me = attrs.get("remember_me", False)

        user: User | None = None
        if "@" in identifier:
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist as exc:
                raise AuthenticationFailed(_("Invalid credentials.")) from exc
        else:
            try:
                profile = Profile.objects.select_related("user").get(phone=identifier)
                user = profile.user
            except Profile.DoesNotExist as exc:
                raise AuthenticationFailed(_("Invalid credentials.")) from exc

        if not user.check_password(password):
            raise AuthenticationFailed(_("Invalid credentials."))

        refresh = RefreshToken.for_user(user)
        if remember_me:
            refresh.set_exp(lifetime=timedelta(days=30))

        access_token = refresh.access_token

        return {
            "access": str(access_token),
            "refresh": str(refresh),
            "user": _build_user_payload(user),
        }


class MeSerializer(serializers.ModelSerializer):
    """Serializer returning the authenticated user's profile."""

    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    phone = serializers.CharField(source="profile.phone", read_only=True)
    role = serializers.CharField(source="profile.role", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "full_name", "phone", "role")
