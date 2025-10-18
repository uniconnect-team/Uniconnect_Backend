"""Serializers for the users app."""
from __future__ import annotations

import random
import re
from datetime import timedelta
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, PendingRegistration, Profile, UniversityDomain
from .services.verification import confirm_code, send_verification


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
    """Serializer for initiating a new user registration."""

    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=Profile.Roles.choices)

    def validate_password(self, value: str) -> str:
        return _validate_password_strength(value)

    def validate_email(self, value: str) -> str:
        value = _normalize_email(value)
        role = self.initial_data.get("role")
        if User.objects.filter(email__iexact=value).exists():
            raise ConflictError(_("A user with this email already exists."))

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

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        email: str = validated_data["email"]
        full_name: str = validated_data.get("full_name", "")
        phone: str = validated_data["phone"]
        role: str = validated_data["role"]
        hashed_password = make_password(validated_data["password"])
        domain = self.context.get("domain")

        PendingRegistration.objects.update_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "phone": phone,
                "password_hash": hashed_password,
                "role": role,
                "university_domain": domain,
                "client_ip": self.context.get("ip"),
                "user_agent": (self.context.get("user_agent", "") or "")[:255],
            },
        )

        send_verification(
            email=email,
            full_name=full_name or email.split("@")[0],
            university_domain=domain.domain if domain else email.split("@")[-1],
            ip=self.context.get("ip"),
        )

        return {
            "ok": True,
            "email": email,
            "cooldownSeconds": self.context.get("cooldown", 60),
            "requiresVerification": True,
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
    """Serializer to request (or resend) an email verification OTP."""

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    role = serializers.ChoiceField(choices=Profile.Roles.choices, required=False)

    def validate_email(self, value: str) -> str:
        return _normalize_email(value)

    def validate_password(self, value: str) -> str:
        return _validate_password_strength(value)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        email = attrs["email"]
        user = User.objects.filter(email__iexact=email).select_related("profile").first()
        pending = PendingRegistration.objects.filter(email__iexact=email).first()
        cooldown_seconds = int(getattr(settings, "VERIFY_RESEND_COOLDOWN_SEC", 60))

        provided_role = attrs.get("role")
        role = provided_role
        if user and getattr(user, "profile", None):
            role = user.profile.role
        elif pending and not role:
            role = pending.role

        missing_fields: Dict[str, list[str]] = {}
        is_new_signup = not user and not pending
        if is_new_signup:
            if not role:
                missing_fields.setdefault("role", []).append(_("This field is required."))
            if not attrs.get("phone"):
                missing_fields.setdefault("phone", []).append(_("This field is required."))
            if not attrs.get("password"):
                missing_fields.setdefault("password", []).append(_("This field is required."))

        if missing_fields:
            raise serializers.ValidationError(missing_fields)

        if not role:
            raise serializers.ValidationError(
                _("Unable to determine the account type for verification."),
                code="invalid_role",
            )

        domain_obj = None
        domain_value = email.split("@")[-1]
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

        phone = attrs.get("phone")
        if phone:
            phone_conflict = Profile.objects.filter(phone=phone).exists()
            if not phone_conflict:
                phone_conflict = (
                    PendingRegistration.objects.filter(phone=phone)
                    .exclude(email__iexact=email)
                    .exists()
                )
            if phone_conflict:
                raise serializers.ValidationError({"phone": [_("Phone number must be unique.")]})

        now = timezone.now()
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

        update_pending = False
        pending_defaults: Dict[str, Any] = {}
        if not user:
            update_pending = True
            base_full_name = attrs.get("full_name") or (pending.full_name if pending else "")
            phone_value = attrs.get("phone") or (pending.phone if pending else None)
            password_value = attrs.get("password")

            if phone_value is None:
                raise serializers.ValidationError({"phone": [_("This field is required.")]})
            if password_value is None and is_new_signup:
                raise serializers.ValidationError({"password": [_("This field is required.")]})

            pending_defaults.update(
                {
                    "full_name": base_full_name,
                    "phone": phone_value,
                    "role": role,
                    "university_domain": domain_obj if role == Profile.Roles.SEEKER else pending.university_domain if pending else domain_obj,
                    "client_ip": self.context.get("ip"),
                    "user_agent": (self.context.get("user_agent", "") or "")[:255],
                }
            )

            if password_value:
                pending_defaults["password_hash"] = make_password(password_value)
            elif pending:
                pending_defaults["password_hash"] = pending.password_hash

            if pending is None and "password_hash" not in pending_defaults:
                raise serializers.ValidationError({"password": [_("This field is required.")]})

        self.context.update(
            {
                "user": user,
                "pending": pending,
                "cooldown": cooldown_seconds,
                "domain": domain_obj,
                "role": role,
                "update_pending": update_pending,
                "pending_defaults": pending_defaults,
                "is_new_signup": is_new_signup,
            }
        )
        return attrs

    def save(self, **kwargs) -> Dict[str, Any]:
        user: User | None = self.context.get("user")
        pending: PendingRegistration | None = self.context.get("pending")
        domain: UniversityDomain | None = self.context.get("domain")
        cooldown_seconds: int = self.context.get("cooldown", 60)
        update_pending: bool = self.context.get("update_pending", False)
        email = self.validated_data["email"]

        if update_pending:
            defaults = self.context.get("pending_defaults", {}).copy()
            defaults.setdefault("full_name", self.validated_data.get("full_name", ""))
            if "password_hash" not in defaults and pending:
                defaults["password_hash"] = pending.password_hash
            pending, _ = PendingRegistration.objects.update_or_create(
                email=email,
                defaults=defaults,
            )
            self.context["pending"] = pending

        full_name = ""
        if user and getattr(user, "profile", None):
            full_name = user.profile.full_name or user.username
        elif pending:
            full_name = pending.full_name or email.split("@")[0]
        else:
            full_name = self.validated_data.get("full_name", "") or email.split("@")[0]

        university_domain = None
        if domain:
            university_domain = domain.domain
        elif pending and pending.university_domain:
            university_domain = pending.university_domain.domain
        else:
            university_domain = email.split("@")[-1]

        send_verification(
            email=email,
            full_name=full_name,
            university_domain=university_domain,
            ip=self.context.get("ip"),
        )

        response: Dict[str, Any] = {
            "ok": True,
            "cooldownSeconds": cooldown_seconds,
        }

        if self.context.get("is_new_signup"):
            response.update({
                "email": email,
                "requiresVerification": True,
            })

        return response


class VerificationConfirmSerializer(serializers.Serializer):
    """Serializer to confirm an email verification OTP."""

    email = serializers.EmailField()
    code = serializers.CharField()

    def validate_email(self, value: str) -> str:
        return _normalize_email(value)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        email = attrs["email"]
        user = User.objects.filter(email__iexact=email).select_related("profile").first()
        pending = PendingRegistration.objects.filter(email__iexact=email).first()
        if not user and not pending:
            raise serializers.ValidationError(
                _("The verification code is invalid."),
                code="invalid_code",
            )
        self.context["user"] = user
        self.context["pending"] = pending
        return attrs

    def save(self, **kwargs) -> Dict[str, Any]:
        user: User | None = self.context.get("user")
        pending: PendingRegistration | None = self.context.get("pending")

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
        created_user = False

        if user is None and pending is not None:
            email = pending.email
            username_base = email.split("@")[0]
            username_candidate = username_base
            while User.objects.filter(username=username_candidate).exists():
                username_candidate = f"{username_base}{random.randint(1000, 9999)}"

            with transaction.atomic():
                user = User(username=username_candidate, email=email)
                user.password = pending.password_hash
                user.save()

                is_student = pending.role == Profile.Roles.SEEKER
                Profile.objects.create(
                    user=user,
                    full_name=pending.full_name,
                    phone=pending.phone,
                    role=pending.role,
                    is_student_verified=is_student,
                    email_verified_at=now,
                    university_domain=pending.university_domain if is_student else None,
                )
                pending.delete()
            created_user = True

        if user is None:
            raise serializers.ValidationError(
                _("Unable to complete verification."),
                code="invalid_code",
            )

        profile = user.profile
        is_student = profile.role == Profile.Roles.SEEKER
        update_fields = ["email_verified_at"]
        profile.email_verified_at = now

        if is_student:
            profile.is_student_verified = True
            update_fields.append("is_student_verified")
            if profile.university_domain is None:
                domain_value = user.email.split("@")[-1]
                domain = UniversityDomain.objects.filter(domain__iexact=domain_value).first()
                profile.university_domain = domain
                update_fields.append("university_domain")

        profile.save(update_fields=update_fields)

        response: Dict[str, Any] = {
            "ok": True,
            "user": _build_user_payload(user),
        }

        if created_user:
            refresh = RefreshToken.for_user(user)
            response.update({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            })

        return response
