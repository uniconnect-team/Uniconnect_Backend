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

from .models import (
    EmailOTP,
    PendingRegistration,
    Profile,
    Property,
    PropertyImage,
    PropertyRoom,
    UniversityDomain,
)


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


def _resolve_default_home_path(profile: Profile | None) -> str:
    """Return the default home path for the given profile role."""

    if not profile:
        return "/home"

    if profile.role == Profile.Roles.OWNER:
        return "/owners/dashboard"

    if profile.role == Profile.Roles.SEEKER:
        return "/seekers/home"

    return "/home"


def _build_user_payload(user: User) -> Dict[str, Any]:
    profile = getattr(user, "profile", None)
    university_domain = getattr(profile, "university_domain", None)
    properties: list[dict[str, Any]] = []
    if profile and profile.role == Profile.Roles.OWNER:
        properties = [
            _serialize_property_summary(prop)
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
        "default_home_path": _resolve_default_home_path(profile),
    }


def _serialize_property_summary(prop: Property) -> dict[str, Any]:
    return {
        "id": prop.id,
        "name": prop.name,
        "location": prop.location,
        "description": prop.description,
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "has_electricity_included": prop.has_electricity_included,
        "has_cleaning_service": prop.has_cleaning_service,
        "additional_services": prop.additional_services,
        "rooms": [
            {
                "id": room.id,
                "room_type": room.room_type,
                "total_rooms": room.total_rooms,
                "available_rooms": room.available_rooms,
                "price_per_month": room.price_per_month,
                "notes": room.notes,
            }
            for room in prop.rooms.all().order_by("room_type")
        ],
        "images": [
            {
                "id": image.id,
                "image_url": image.image_url,
                "caption": image.caption,
            }
            for image in prop.images.all().order_by("-uploaded_at")
        ],
        "created_at": prop.created_at,
        "updated_at": prop.updated_at,
    }


def _create_property_with_nested(owner: Profile, property_data: dict[str, Any]) -> Property:
    images_data = property_data.pop("images", [])
    rooms_data = property_data.pop("rooms", [])
    property_obj = Property.objects.create(owner=owner, **property_data)
    _replace_property_images(property_obj, images_data)
    _replace_property_rooms(property_obj, rooms_data)
    return property_obj


def _replace_property_images(property_obj: Property, images_data: list[dict[str, Any]]) -> None:
    property_obj.images.all().delete()
    PropertyImage.objects.bulk_create(
        [
            PropertyImage(
                property=property_obj,
                image_url=image_info["image_url"],
                caption=image_info.get("caption", ""),
            )
            for image_info in images_data
        ]
    )


def _replace_property_rooms(property_obj: Property, rooms_data: list[dict[str, Any]]) -> None:
    property_obj.rooms.all().delete()
    PropertyRoom.objects.bulk_create(
        [
            PropertyRoom(
                property=property_obj,
                room_type=room_info["room_type"],
                total_rooms=room_info["total_rooms"],
                available_rooms=room_info["available_rooms"],
                price_per_month=room_info.get("price_per_month"),
                notes=room_info.get("notes", ""),
            )
            for room_info in rooms_data
        ]
    )


class PropertyImageSerializer(serializers.ModelSerializer):
    """Serializer for property images."""

    class Meta:
        model = PropertyImage
        fields = ("id", "image_url", "caption", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


class PropertyRoomSerializer(serializers.ModelSerializer):
    """Serializer describing room availability for a property."""

    class Meta:
        model = PropertyRoom
        fields = (
            "id",
            "room_type",
            "total_rooms",
            "available_rooms",
            "price_per_month",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        total_rooms = attrs.get("total_rooms", getattr(self.instance, "total_rooms", 0))
        available_rooms = attrs.get(
            "available_rooms",
            getattr(self.instance, "available_rooms", 0),
        )
        if available_rooms > total_rooms:
            raise serializers.ValidationError(
                _("Available rooms cannot exceed the total number of rooms."),
            )
        return attrs


class PropertySerializer(serializers.ModelSerializer):
    """Serializer used for creating and updating owner properties."""

    images = PropertyImageSerializer(many=True, required=False)
    rooms = PropertyRoomSerializer(many=True, required=False)

    class Meta:
        model = Property
        fields = (
            "id",
            "name",
            "location",
            "description",
            "latitude",
            "longitude",
            "has_electricity_included",
            "has_cleaning_service",
            "additional_services",
            "images",
            "rooms",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_rooms(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if value is None:
            return []
        seen: set[tuple[str, str]] = set()
        for room in value:
            key = (room["room_type"], room.get("notes", ""))
            if key in seen:
                raise serializers.ValidationError(
                    _("Room entries must be unique for each type and notes combination."),
                )
            seen.add(key)
        return value

    def validate_images(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if value is None:
            return []
        seen_urls: set[str] = set()
        for image in value:
            url = image["image_url"].strip()
            if url in seen_urls:
                raise serializers.ValidationError(
                    _("Duplicate image URLs are not allowed."),
                )
            seen_urls.add(url)
        return value

    def create(self, validated_data: dict[str, Any]) -> Property:
        owner: Profile | None = self.context.get("owner")
        owner = validated_data.pop("owner", owner)
        if owner is None:
            raise serializers.ValidationError({"owner": _("Owner profile is required.")})
        return _create_property_with_nested(owner, validated_data)

    def update(self, instance: Property, validated_data: dict[str, Any]) -> Property:
        images_data = validated_data.pop("images", None)
        rooms_data = validated_data.pop("rooms", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if images_data is not None:
            _replace_property_images(instance, images_data)
        if rooms_data is not None:
            _replace_property_rooms(instance, rooms_data)

        return instance


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
        description = serializers.CharField(required=False, allow_blank=True)
        latitude = serializers.DecimalField(
            max_digits=9,
            decimal_places=6,
            required=False,
            allow_null=True,
        )
        longitude = serializers.DecimalField(
            max_digits=9,
            decimal_places=6,
            required=False,
            allow_null=True,
        )
        has_electricity_included = serializers.BooleanField(required=False)
        has_cleaning_service = serializers.BooleanField(required=False)
        additional_services = serializers.CharField(required=False, allow_blank=True)
        images = PropertyImageSerializer(many=True, required=False)
        rooms = PropertyRoomSerializer(many=True, required=False)

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

        cleaned: list[dict[str, Any]] = []
        for property_data in value:
            serializer = PropertySerializer(data=property_data)
            serializer.is_valid(raise_exception=True)
            cleaned.append(serializer.validated_data)
        return cleaned

    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        properties_data = validated_data.pop("properties", [])

        with transaction.atomic():
            user, profile = self._create_user_and_profile(validated_data)
            for property_info in properties_data:
                _create_property_with_nested(profile, property_info)

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
    default_home_path = serializers.SerializerMethodField()

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
            "default_home_path",
        )

    def get_properties(self, obj: User) -> list[dict[str, Any]]:
        profile = getattr(obj, "profile", None)
        if not profile or profile.role != Profile.Roles.OWNER:
            return []
        return [
            _serialize_property_summary(prop)
            for prop in profile.properties.all().order_by("name")
        ]

    def get_default_home_path(self, obj: User) -> str:
        profile = getattr(obj, "profile", None)
        return _resolve_default_home_path(profile)
