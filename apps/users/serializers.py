"""Serializers for the users app."""
from __future__ import annotations

import random
import re
from datetime import timedelta
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, Profile, UniversityDomain
from .services.verification import confirm_code, send_verification


UNIVERSITY_EMAIL_ERROR_CODE = "UNIVERSITY_EMAIL_REQUIRED"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _build_user_payload(user: User) -> Dict[str, Any]:
    profile = getattr(user, "profile", None)
    university_domain = getattr(profile, "university_domain", None)
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
    is_student_verified = serializers.BooleanField(read_only=True)
    email_verified_at = serializers.DateTimeField(read_only=True)
    university_domain = serializers.CharField(read_only=True)

    def validate_password(self, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise serializers.ValidationError(
                _("Password must contain at least one letter and one digit."),
                code="invalid_password",
            )
        return value

    def validate_email(self, value: str) -> str:
        value = _normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise ConflictError(_("A user with this email already exists."))
        role = self.initial_data.get("role")
        if role == Profile.Roles.SEEKER:
            domain = value.split("@")[-1]
            if not UniversityDomain.objects.filter(domain__iexact=domain, is_active=True).exists():
                raise serializers.ValidationError(
                    _("A valid Lebanese university email is required."),
                    code=UNIVERSITY_EMAIL_ERROR_CODE,
                )
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
    is_student_verified = serializers.BooleanField(source="profile.is_student_verified", read_only=True)
    email_verified_at = serializers.DateTimeField(source="profile.email_verified_at", read_only=True)
    university_domain = serializers.CharField(
        source="profile.university_domain.domain", read_only=True, default=""
    )

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
        )


class VerificationRequestSerializer(serializers.Serializer):
    """Serializer to request an email verification OTP."""

    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        normalized = _normalize_email(value)
        domain_value = normalized.split("@")[-1]
        try:
            domain = UniversityDomain.objects.get(domain__iexact=domain_value, is_active=True)
        except UniversityDomain.DoesNotExist as exc:
            raise serializers.ValidationError(
                _("A valid Lebanese university email is required."),
                code=UNIVERSITY_EMAIL_ERROR_CODE,
            ) from exc
        self.context["domain"] = domain
        return normalized

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        email = attrs["email"]
        user = User.objects.filter(email__iexact=email).select_related("profile").first()
        self.context["user"] = user
        self.context["cooldown"] = getattr(settings, "VERIFY_RESEND_COOLDOWN_SEC", 60)
        if not user:
            return attrs

        profile = getattr(user, "profile", None)
        if profile and profile.role != Profile.Roles.SEEKER:
            raise serializers.ValidationError(
                _("Email verification is only available for student accounts."),
                code="invalid_role",
            )

        now = timezone.now()
        cooldown_seconds = self.context["cooldown"]
        recent_token = (
            EmailOTP.objects.filter(email=email)
            .order_by("-created_at")
            .first()
        )
        if recent_token and recent_token.created_at + timedelta(seconds=cooldown_seconds) > now:
            raise serializers.ValidationError(
                _("Please wait before requesting a new verification code."),
                code="cooldown_active",
            )

        daily_limit = getattr(settings, "VERIFY_MAX_DAILY_SENDS", 5)
        day_start = now - timedelta(hours=24)
        sent_today = EmailOTP.objects.filter(
            email=email,
            created_at__gte=day_start,
        ).count()
        if sent_today >= daily_limit:
            raise serializers.ValidationError(
                _("Maximum verification attempts reached. Please try again later."),
                code="rate_limited",
            )
        return attrs

    def save(self, **kwargs) -> Dict[str, Any]:
        user: User | None = self.context.get("user")
        domain: UniversityDomain = self.context["domain"]
        cooldown_seconds: int = self.context["cooldown"]
        email = self.validated_data["email"]
        if not user:
            return {"ok": True, "cooldownSeconds": cooldown_seconds}

        send_verification(
            email=email,
            full_name=getattr(user.profile, "full_name", user.username),
            university_domain=domain.domain,
            ip=self.context.get("ip"),
        )

        return {"ok": True, "cooldownSeconds": cooldown_seconds}


class VerificationConfirmSerializer(serializers.Serializer):
    """Serializer to confirm an email verification OTP."""

    email = serializers.EmailField()
    code = serializers.CharField()

    def validate_email(self, value: str) -> str:
        return _normalize_email(value)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        email = attrs["email"]
        user = User.objects.filter(email__iexact=email).select_related("profile").first()
        if not user:
            raise serializers.ValidationError(
                _("The verification code is invalid."),
                code="invalid_code",
            )
        self.context["user"] = user
        return attrs

    def save(self, **kwargs) -> Dict[str, Any]:
        user: User = self.context["user"]
        profile = user.profile

        success, result = confirm_code(
            email=self.validated_data["email"],
            code=self.validated_data["code"],
        )

        if not success:
            if result == "expired":
                raise serializers.ValidationError(
                    _("The verification code has expired."),
                    code="expired_code",
                )
            raise serializers.ValidationError(
                _("The verification code is invalid."),
                code="invalid_code",
            )

        otp: EmailOTP = result
        now = timezone.now()
        profile.is_student_verified = True
        profile.email_verified_at = now

        domain_value = user.email.split("@")[-1]
        domain = UniversityDomain.objects.filter(domain__iexact=domain_value).first()
        profile.university_domain = domain
        profile.save(update_fields=["is_student_verified", "email_verified_at", "university_domain"])
        if otp.used_at is None:
            otp.used_at = now
            otp.save(update_fields=["used_at"])

        return {"ok": True}
