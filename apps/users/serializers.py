"""Serializers for the users app."""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, PendingRegistration, Profile, Property, UniversityDomain


UNIVERSITY_EMAIL_ERROR_CODE = "UNIVERSITY_EMAIL_REQUIRED"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_password_strength(value: str) -> str:
    """Ensure the supplied password contains both letters and digits."""

    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise serializers.ValidationError(
            _("Password must contain at least one letter and one digit."),
            code="invalid_password",
        )
    return value


def _build_user_payload(user: User) -> Dict[str, Any]:
    profile = getattr(user, "profile", None)
    university_domain = getattr(profile, "university_domain", None)
    properties: list[dict[str, Any]] = []
    if profile and profile.role == Profile.Roles.OWNER:
        properties = [
            {
                "id": prop.id,
                "name": prop.name,
                "location": prop.location,
            }
            for prop in profile.properties.all().order_by("name")
        ]
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": getattr(profile, "full_name", ""),
        "phone": getattr(profile, "phone", ""),
        "role": getattr(profile, "role", ""),
        "is_student_verified": getattr(profile, "is_student_verified", False),
        "email_verified_at": getattr(profile, "email_verified_at", None),
        "university_domain": getattr(university_domain, "domain", ""),
        "properties": properties,
    }


class RegisterSerializer(serializers.Serializer):
    """Serializer for creating a new user account."""

    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=Profile.Roles.choices)

    def validate_password(self, value: str) -> str:  # noqa: D401 - delegated helper
        return _validate_password_strength(value)

    def validate_email(self, value: str) -> str:
        value = _normalize_email(value)
        role = self.initial_data.get("role")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists."),
                code="duplicate_email",
            )

        domain_value = value.split("@")[-1]
        domain_obj = None
        if role == Profile.Roles.SEEKER:
            try:
                domain_obj = UniversityDomain.objects.get(
                    domain__iexact=domain_value,
                    is_active=True,
                )
            except UniversityDomain.DoesNotExist as exc:
                raise serializers.ValidationError(
                    _("A valid Lebanese university email is required."),
                    code=UNIVERSITY_EMAIL_ERROR_CODE,
                ) from exc
        else:
            domain_obj = (
                UniversityDomain.objects.filter(domain__iexact=domain_value, is_active=True)
                .order_by("-created_at")
                .first()
            )

        self.context["domain"] = domain_obj
        return value

    def validate_phone(self, value: str) -> str:
        if Profile.objects.filter(phone=value).exists():
            raise serializers.ValidationError(_("Phone number must be unique."))
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        email = attrs["email"]
        phone = attrs["phone"]
        cooldown_seconds = int(getattr(settings, "VERIFY_RESEND_COOLDOWN_SEC", 60))
        now = timezone.now()

        if Profile.objects.filter(phone=phone).exists():
            raise serializers.ValidationError(
                {"phone": [_("Phone number must be unique.")]}
            )

        pending_conflict = (
            PendingRegistration.objects.filter(phone=phone)
            .exclude(email__iexact=email)
            .exists()
        )
        if pending_conflict:
            raise serializers.ValidationError(
                {"phone": [_("Phone number must be unique.")]}
            )

        recent_token = EmailOTP.objects.filter(email=email).order_by("-created_at").first()
        if recent_token and recent_token.created_at + timedelta(seconds=cooldown_seconds) > now:
            raise serializers.ValidationError(
                _("Please wait before requesting a new verification code."),
                code="cooldown_active",
            )

        daily_limit = int(getattr(settings, "VERIFY_MAX_DAILY_SENDS", 5))
        sent_today = EmailOTP.objects.filter(
            email=email,
            created_at__gte=now - timedelta(hours=24),
        ).count()
        if sent_today >= daily_limit:
            raise serializers.ValidationError(
                _("Maximum verification attempts reached. Please try again later."),
                code="rate_limited",
            )

        self.context["cooldown"] = cooldown_seconds
        return attrs

    def _create_user_and_profile(self, validated_data: Dict[str, Any]) -> tuple[User, Profile]:
        email: str = validated_data["email"]
        phone: str = validated_data["phone"]
        role: str = validated_data["role"]
        full_name: str = validated_data.get("full_name", "")
        password: str = validated_data["password"]
        domain = self.context.get("domain")

        username_base = email.split("@")[0]
        username_candidate = username_base
        suffix = 1
        while User.objects.filter(username__iexact=username_candidate).exists():
            suffix += 1
            username_candidate = f"{username_base}{suffix}"

        user = User.objects.create_user(
            username=username_candidate,
            email=email,
            password=password,
        )

        is_student = role == Profile.Roles.SEEKER
        profile = Profile.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            role=role,
            is_student_verified=is_student,
            email_verified_at=timezone.now() if is_student else None,
            university_domain=domain if is_student else None,
        )
        return user, profile

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        with transaction.atomic():
            user, _profile = self._create_user_and_profile(validated_data)

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": _build_user_payload(user),
        }


class OwnerRegisterSerializer(RegisterSerializer):
    """Serializer for dorm owners registering their properties."""

    class PropertyInputSerializer(serializers.Serializer):
        name = serializers.CharField(max_length=255)
        location = serializers.CharField(max_length=255)

    properties = PropertyInputSerializer(many=True)
    role = serializers.HiddenField(default=Profile.Roles.OWNER)

    def validate_email(self, value: str) -> str:  # noqa: D401 - delegated helper
        value = _normalize_email(value)

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists."),
                code="duplicate_email",
            )

        domain_value = value.split("@")[-1]
        domain_obj = (
            UniversityDomain.objects.filter(domain__iexact=domain_value, is_active=True)
            .order_by("-created_at")
            .first()
        )

        self.context["domain"] = domain_obj
        return value

    def validate_properties(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not value:
            raise serializers.ValidationError(
                _("At least one property must be provided for registration."),
                code="invalid",
            )
        return value

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        properties_data = validated_data.pop("properties", [])

        with transaction.atomic():
            user, profile = self._create_user_and_profile(validated_data)
            for property_info in properties_data:
                Property.objects.create(
                    owner=profile,
                    name=property_info["name"],
                    location=property_info["location"],
                )

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": _build_user_payload(user),
        }


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
    is_student_verified = serializers.BooleanField(source="profile.is_student_verified", read_only=True)
    email_verified_at = serializers.DateTimeField(source="profile.email_verified_at", read_only=True)
    university_domain = serializers.CharField(
        source="profile.university_domain.domain", read_only=True, default=""
    )
    properties = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "phone",
            "role",
            "is_student_verified",
            "email_verified_at",
            "university_domain",
            "properties",
        )

    def get_properties(self, obj: User) -> list[dict[str, Any]]:
        profile = getattr(obj, "profile", None)
        if not profile or profile.role != Profile.Roles.OWNER:
            return []
        return [
            {
                "id": prop.id,
                "name": prop.name,
                "location": prop.location,
            }
            for prop in profile.properties.all().order_by("name")
        ]
