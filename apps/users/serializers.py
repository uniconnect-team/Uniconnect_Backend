"""Serializers for the users app."""
from __future__ import annotations

import re
from datetime import date, timedelta
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
    Room,
    RoomImage,
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
    
    # Check if profile is incomplete - redirect to role-specific completion page
    if not profile.profile_completed:
        if profile.role == Profile.Roles.OWNER:
            return "/complete-profile/owner"
        if profile.role == Profile.Roles.SEEKER:
            return "/complete-profile/seeker"
        return "/complete-profile/seeker"

    # Profile is complete - go to role-specific home
    if profile.role == Profile.Roles.OWNER:
        return "/owners/properties"

    if profile.role == Profile.Roles.SEEKER:
        return "/seekers/home"

    return "/home"


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
                "cover_image": prop.cover_image.url if prop.cover_image else "",
                "rooms_count": prop.rooms.count(),
                "electricity_included": prop.electricity_included,
                "cleaning_included": prop.cleaning_included,
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
        "date_of_birth": getattr(profile, "date_of_birth", None),
        "profile_completed": getattr(profile, "profile_completed", False),
        "properties": properties,
        "default_home_path": _resolve_default_home_path(profile),
    }


class PropertyImageNestedSerializer(serializers.ModelSerializer):
    """Serializer for property gallery images nested under a property."""

    class Meta:
        model = PropertyImage
        fields = ("id", "image", "caption", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


class RoomImageNestedSerializer(serializers.ModelSerializer):
    """Serializer for room gallery images nested under a room."""

    class Meta:
        model = RoomImage
        fields = ("id", "image", "caption", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


class RoomNestedSerializer(serializers.ModelSerializer):
    """Nested room serializer used when working through the property serializer."""

    images = RoomImageNestedSerializer(many=True, required=False)

    class Meta:
        model = Room
        fields = (
            "id",
            "name",
            "room_type",
            "description",
            "price_per_month",
            "capacity",
            "available_quantity",
            "amenities",
            "electricity_included",
            "cleaning_included",
            "is_active",
            "images",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_amenities(self, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Amenities must be provided as a list of strings.")
        return value


class PropertySerializer(serializers.ModelSerializer):
    """Serializer for creating and updating owner properties."""

    images = PropertyImageNestedSerializer(many=True, required=False)
    rooms = RoomNestedSerializer(many=True, required=False)

    class Meta:
        model = Property
        fields = (
            "id",
            "name",
            "location",
            "description",
            "cover_image",
            "amenities",
            "electricity_included",
            "cleaning_included",
            "images",
            "rooms",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_amenities(self, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Amenities must be provided as a list of strings.")
        return value

    def create(self, validated_data: Dict[str, Any]) -> Property:
        images_data = validated_data.pop("images", [])
        rooms_data = validated_data.pop("rooms", [])
        owner = self.context.get("owner")
        if not owner:
            raise serializers.ValidationError("Owner context is required to create properties.")

        property_obj = Property.objects.create(owner=owner, **validated_data)
        self._sync_property_images(property_obj, images_data)
        self._sync_rooms(property_obj, rooms_data)
        return property_obj

    def update(self, instance: Property, validated_data: Dict[str, Any]) -> Property:
        images_data = validated_data.pop("images", None)
        rooms_data = validated_data.pop("rooms", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if images_data is not None or "images" in self.initial_data:
            instance.images.all().delete()
            self._sync_property_images(instance, images_data or [])

        if rooms_data is not None or "rooms" in self.initial_data:
            instance.rooms.all().delete()
            self._sync_rooms(instance, rooms_data or [])

        return instance

    def _sync_property_images(self, property_obj: Property, images_data: list[dict[str, Any]]) -> None:
        for image_data in images_data:
            PropertyImage.objects.create(property=property_obj, **image_data)

    def _sync_rooms(self, property_obj: Property, rooms_data: list[dict[str, Any]]) -> None:
        for room_data in rooms_data:
            images_data = room_data.pop("images", [])
            room = Room.objects.create(property=property_obj, **room_data)
            for image_data in images_data:
                RoomImage.objects.create(room=room, **image_data)


class PropertyImageSerializer(serializers.ModelSerializer):
    """Serializer for standalone property image operations."""

    class Meta:
        model = PropertyImage
        fields = ("id", "property", "image", "caption", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")

    def validate_property(self, value: Property) -> Property:
        owner = self.context.get("owner")
        if owner and value.owner != owner:
            raise serializers.ValidationError("You can only manage images for your own properties.")
        return value


class RoomImageSerializer(serializers.ModelSerializer):
    """Serializer for standalone room image operations."""

    class Meta:
        model = RoomImage
        fields = ("id", "room", "image", "caption", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")

    def validate_room(self, value: Room) -> Room:
        owner = self.context.get("owner")
        if owner and value.property.owner != owner:
            raise serializers.ValidationError("You can only manage images for your own rooms.")
        return value


class RoomSerializer(serializers.ModelSerializer):
    """Serializer for owner room management endpoints."""

    images = RoomImageNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Room
        fields = (
            "id",
            "property",
            "name",
            "room_type",
            "description",
            "price_per_month",
            "capacity",
            "available_quantity",
            "amenities",
            "electricity_included",
            "cleaning_included",
            "is_active",
            "images",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_property(self, value: Property) -> Property:
        owner = self.context.get("owner")
        if owner and value.owner != owner:
            raise serializers.ValidationError("You can only manage rooms for your own properties.")
        return value

    def validate_amenities(self, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Amenities must be provided as a list of strings.")
        return value

class RegisterSerializer(serializers.Serializer):
    """Serializer for creating a new user account."""

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
            profile_completed=False,  # ALWAYS False on registration
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
        cover_image = serializers.ImageField(required=False, allow_null=True)
        amenities = serializers.ListField(
            child=serializers.CharField(), required=False, allow_empty=True
        )
        electricity_included = serializers.BooleanField(required=False, default=False)
        cleaning_included = serializers.BooleanField(required=False, default=False)

        class RoomInputSerializer(serializers.Serializer):
            name = serializers.CharField(max_length=255)
            room_type = serializers.ChoiceField(choices=Room.RoomType.choices)
            description = serializers.CharField(required=False, allow_blank=True)
            price_per_month = serializers.DecimalField(max_digits=8, decimal_places=2)
            capacity = serializers.IntegerField(min_value=1, default=1)
            available_quantity = serializers.IntegerField(min_value=0, default=0)
            amenities = serializers.ListField(
                child=serializers.CharField(), required=False, allow_empty=True
            )
            electricity_included = serializers.BooleanField(
                required=False, default=False
            )
            cleaning_included = serializers.BooleanField(required=False, default=False)
            is_active = serializers.BooleanField(required=False, default=True)
            images = RoomImageNestedSerializer(many=True, required=False)

        rooms = RoomInputSerializer(many=True, required=False)
        images = PropertyImageNestedSerializer(many=True, required=False)

    properties = PropertyInputSerializer(many=True)
    role = serializers.HiddenField(default=Profile.Roles.OWNER)

    def validate_email(self, value: str) -> str:
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
                rooms_data = property_info.pop("rooms", [])
                images_data = property_info.pop("images", [])
                amenities = property_info.pop("amenities", []) or []
                property_obj = Property.objects.create(
                    owner=profile,
                    name=property_info["name"],
                    location=property_info["location"],
                    description=property_info.get("description", ""),
                    cover_image=property_info.get("cover_image"),
                    amenities=amenities,
                    electricity_included=property_info.get("electricity_included", False),
                    cleaning_included=property_info.get("cleaning_included", False),
                )
                for image in images_data:
                    PropertyImage.objects.create(property=property_obj, **image)
                for room_info in rooms_data:
                    room_images = room_info.pop("images", [])
                    amenities = room_info.pop("amenities", []) or []
                    room = Room.objects.create(
                        property=property_obj,
                        name=room_info["name"],
                        room_type=room_info["room_type"],
                        description=room_info.get("description", ""),
                        price_per_month=room_info["price_per_month"],
                        capacity=room_info.get("capacity", 1),
                        available_quantity=room_info.get("available_quantity", 0),
                        amenities=amenities,
                        electricity_included=room_info.get("electricity_included", False),
                        cleaning_included=room_info.get("cleaning_included", False),
                        is_active=room_info.get("is_active", True),
                    )
                    for image in room_images:
                        RoomImage.objects.create(room=room, **image)

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


class ProfileCompletionSerializer(serializers.Serializer):
    """Base serializer for completing user profiles after registration."""
    
    full_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20)
    
    def validate_phone(self, value: str) -> str:
        user = self.context.get('user')
        # Allow keeping the same phone or changing to a new unique one
        existing = Profile.objects.filter(phone=value).exclude(user=user).exists()
        if existing:
            raise serializers.ValidationError(_("Phone number must be unique."))
        return value
    
    def update_profile(self, user: User, validated_data: Dict[str, Any]) -> Profile:
        profile = user.profile
        profile.full_name = validated_data['full_name']
        profile.phone = validated_data['phone']
        profile.profile_completed = True
        profile.save()
        return profile


class SeekerProfileCompletionSerializer(ProfileCompletionSerializer):
    """Serializer for seekers to complete their profile."""
    
    date_of_birth = serializers.DateField()
    
    def validate_date_of_birth(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 16:
            raise serializers.ValidationError(_("You must be at least 16 years old."))
        if age > 100:
            raise serializers.ValidationError(_("Please enter a valid date of birth."))
        return value
    
    def update_profile(self, user: User, validated_data: Dict[str, Any]) -> Profile:
        profile = super().update_profile(user, validated_data)
        profile.date_of_birth = validated_data['date_of_birth']
        profile.save()
        return profile


class OwnerProfileCompletionSerializer(ProfileCompletionSerializer):
    """Serializer for owners to complete their profile."""
    
    email = serializers.EmailField()
    
    def validate_email(self, value: str) -> str:
        user = self.context.get('user')
        value = _normalize_email(value)
        # Allow keeping the same email or changing to a new unique one
        existing = User.objects.filter(email__iexact=value).exclude(id=user.id).exists()
        if existing:
            raise serializers.ValidationError(_("Email already in use."))
        return value
    
    def update_profile(self, user: User, validated_data: Dict[str, Any]) -> Profile:
        profile = super().update_profile(user, validated_data)
        # Update user email if owner wants to change it
        email = validated_data.get('email')
        if email and email != user.email:
            user.email = email
            user.save()
        return profile


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
    date_of_birth = serializers.DateField(source="profile.date_of_birth", read_only=True)
    profile_completed = serializers.BooleanField(source="profile.profile_completed", read_only=True)
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
            "date_of_birth",
            "profile_completed",
            "properties",
            "default_home_path",
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

    def get_default_home_path(self, obj: User) -> str:
        profile = getattr(obj, "profile", None)
        return _resolve_default_home_path(profile)