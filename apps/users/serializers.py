"""Serializers for the users app."""
from __future__ import annotations

import math
import random
import re
from datetime import timedelta
from typing import Any, Dict
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile, VerificationToken
from .services.verification import (
    VerificationFailure,
    confirm_verification,
    extract_domain,
    get_matching_domain,
    normalize_email,
    request_verification,
)

logger = logging.getLogger(__name__)


def _build_user_payload(user: User) -> Dict[str, Any]:
    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": getattr(profile, "full_name", ""),
        "phone": getattr(profile, "phone", ""),
        "role": getattr(profile, "role", ""),
        "email_verified_at": getattr(profile, "email_verified_at", None),
        "is_student_verified": getattr(profile, "is_student_verified", False),
        "university_domain": getattr(profile, "university_domain", ""),
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
    email_verified_at = serializers.DateTimeField(source="profile.email_verified_at", read_only=True)
    is_student_verified = serializers.BooleanField(source="profile.is_student_verified", read_only=True)
    university_domain = serializers.CharField(source="profile.university_domain", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "phone",
            "role",
            "email_verified_at",
            "is_student_verified",
            "university_domain",
        )


class VerifyEmailRequestSerializer(serializers.Serializer):
    """Serializer validating verification email requests."""

    email = serializers.EmailField()

    default_error_messages = {
        "domain_not_allowed": _("Use a university email address from our supported institutions."),
        "cooldown": _("Please wait {seconds} seconds before requesting another verification email."),
        "daily_limit": _("You reached today's verification email limit. Try again later."),
        "email_in_use": _("This email is already associated with another account."),
    }

    def validate_email(self, value: str) -> str:
        normalized = normalize_email(value)
        domain = extract_domain(normalized)
        university = get_matching_domain(domain)
        if not university:
            raise serializers.ValidationError(
                self.error_messages["domain_not_allowed"], code="domain_not_allowed"
            )
        self.university = university
        return normalized

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        user: User = self.context["request"].user
        email: str = attrs["email"]
        now = timezone.now()
        cooldown_seconds = getattr(settings, "VERIFY_RESEND_COOLDOWN_SEC", 60)

        tokens_qs = (
            VerificationToken.objects.for_user(user)
            .filter(token_type=VerificationToken.Types.LINK)
            .order_by("-created_at")
        )
        last_token = tokens_qs.first()
        if last_token:
            elapsed = (now - last_token.created_at).total_seconds()
            if elapsed < cooldown_seconds:
                remaining = max(1, math.ceil(cooldown_seconds - elapsed))
                message = self.error_messages["cooldown"].format(seconds=remaining)
                raise serializers.ValidationError(message, code="cooldown")

        daily_limit = getattr(settings, "VERIFY_DAILY_LIMIT", 5)
        window_start = now - timedelta(days=1)
        sends_last_day = tokens_qs.filter(created_at__gte=window_start).count()
        if sends_last_day >= daily_limit:
            raise serializers.ValidationError(self.error_messages["daily_limit"], code="daily_limit")

        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(self.error_messages["email_in_use"], code="email_in_use")

        self.cooldown_seconds = cooldown_seconds
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context["request"]
        try:
            result = request_verification(
                user=request.user,
                email=validated_data["email"],
                university=self.university,
                created_ip=request.META.get("REMOTE_ADDR"),
                created_ua=request.META.get("HTTP_USER_AGENT", ""),
            )
        except ValueError as exc:
            raise serializers.ValidationError(str(exc), code="email_in_use") from exc

        return {
            "cooldown_seconds": result.cooldown_seconds,
            "expires_at": result.expires_at,
        }


class VerifyEmailConfirmSerializer(serializers.Serializer):
    """Serializer for confirming verification tokens."""

    token = serializers.CharField()

    default_error_messages = {
        "invalid": _("Verification link is invalid or has expired."),
        "locked": _("Too many invalid attempts. Please request a new verification email."),
    }

    def validate_token(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError(_("Token is required."), code="required")
        return cleaned

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        token = validated_data["token"]
        try:
            confirm_verification(token)
        except VerificationFailure as exc:
            raise serializers.ValidationError(str(exc), code=exc.code) from exc
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unexpected verification failure")
            raise serializers.ValidationError(self.error_messages["invalid"], code="invalid") from exc

        return {"ok": True}
