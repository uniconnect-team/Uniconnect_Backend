"""Serializers for the users app."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from services.media.serializers import (
    AbsoluteURLImageField,
    DormImageSerializer,
    DormRoomImageSerializer,
)

from .models import (
    BookingRequest,
    Dorm,
    DormImage,
    DormRoom,
    DormRoomImage,
    EmailOTP,
    PendingRegistration,
    Profile,
    Property,
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
        return "/owners/dashboard"

    if profile.role == Profile.Roles.SEEKER:
        return "/seekers/home"

    return "/home"


def _build_user_payload(user: User) -> Dict[str, Any]:
    profile = getattr(user, "profile", None)
    university_domain = getattr(profile, "university_domain", None)
    properties: list[dict[str, Any]] = []
    dorms: list[dict[str, Any]] = []
    if profile and profile.role == Profile.Roles.OWNER:
        properties = [
            {
                "id": prop.id,
                "name": prop.name,
                "location": prop.location,
            }
            for prop in profile.properties.all().order_by("name")
        ]
        dorms = [
            {
                "id": dorm.id,
                "name": dorm.name,
                "property": {
                    "id": dorm.property_id,
                    "name": dorm.property.name,
                },
                "cover_image": dorm.cover_image.url if dorm.cover_image else "",
                "is_active": dorm.is_active,
            }
            for dorm in Dorm.objects.filter(property__owner=profile).select_related("property")
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
        "dorms": dorms,
        "default_home_path": _resolve_default_home_path(profile),
    }


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
    dorms = serializers.SerializerMethodField()
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
            "dorms",
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

    def get_dorms(self, obj: User) -> list[dict[str, Any]]:
        profile = getattr(obj, "profile", None)
        if not profile or profile.role != Profile.Roles.OWNER:
            return []
        dorms = (
            Dorm.objects.filter(property__owner=profile)
            .select_related("property")
            .order_by("name")
        )
        return [
            {
                "id": dorm.id,
                "name": dorm.name,
                "property": {
                    "id": dorm.property_id,
                    "name": dorm.property.name,
                },
                "cover_image": dorm.cover_image.url if dorm.cover_image else "",
                "is_active": dorm.is_active,
            }
            for dorm in dorms
        ]

    def get_default_home_path(self, obj: User) -> str:
        profile = getattr(obj, "profile", None)
        return _resolve_default_home_path(profile)


class DormRoomSerializer(serializers.ModelSerializer):
    """Serializer for dorm room management."""

    images = DormRoomImageSerializer(many=True, read_only=True)

    class Meta:
        model = DormRoom
        fields = (
            "id",
            "dorm",
            "name",
            "room_type",
            "capacity",
            "price_per_month",
            "amenities",
            "total_units",
            "available_units",
            "is_available",
            "images",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request.user, "profile"):
            profile = request.user.profile
            self.fields["dorm"].queryset = Dorm.objects.filter(property__owner=profile)
        else:
            self.fields["dorm"].queryset = Dorm.objects.none()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        total_units = attrs.get("total_units", getattr(self.instance, "total_units", 1))
        available_units = attrs.get(
            "available_units",
            getattr(self.instance, "available_units", total_units),
        )
        if available_units > total_units:
            raise serializers.ValidationError(
                {"available_units": _("Available units cannot exceed total units.")}
            )
        return attrs


class DormSerializer(serializers.ModelSerializer):
    """Serializer for dorm management including nested resources."""

    rooms = DormRoomSerializer(many=True, read_only=True)
    images = DormImageSerializer(many=True, read_only=True)

    class Meta:
        model = Dorm
        fields = (
            "id",
            "property",
            "name",
            "description",
            "cover_image",
            "amenities",
            "room_service_available",
            "electricity_included",
            "water_included",
            "internet_included",
            "is_active",
            "rooms",
            "images",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request.user, "profile"):
            profile = request.user.profile
            self.fields["property"].queryset = Property.objects.filter(owner=profile)
        else:
            self.fields["property"].queryset = Property.objects.none()


class BookingRequestSerializer(serializers.ModelSerializer):
    """Serializer used for owner booking request management."""

    dorm = serializers.SerializerMethodField()
    room = serializers.PrimaryKeyRelatedField(queryset=DormRoom.objects.none())

    class Meta:
        model = BookingRequest
        fields = (
            "id",
            "room",
            "dorm",
            "seeker_name",
            "seeker_email",
            "seeker_phone",
            "message",
            "move_in_date",
            "move_out_date",
            "status",
            "owner_note",
            "responded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "responded_at", "created_at", "updated_at", "dorm")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request.user, "profile"):
            profile = request.user.profile
            self.fields["room"].queryset = DormRoom.objects.filter(dorm__property__owner=profile)
        else:
            self.fields["room"].queryset = DormRoom.objects.none()

    def get_dorm(self, obj: BookingRequest) -> dict[str, Any]:
        dorm = obj.room.dorm
        return {
            "id": dorm.id,
            "name": dorm.name,
            "property": {
                "id": dorm.property_id,
                "name": dorm.property.name,
            },
        }

    def validate_room(self, value: DormRoom) -> DormRoom:
        if self.instance and value != self.instance.room:
            raise serializers.ValidationError(_("Room cannot be changed once created."))
        return value

    def update(self, instance: BookingRequest, validated_data: Dict[str, Any]) -> BookingRequest:
        previous_status = instance.status
        instance = super().update(instance, validated_data)
        if previous_status != instance.status and instance.status != BookingRequest.Status.PENDING:
            instance.responded_at = timezone.now()
            instance.save(update_fields=["responded_at", "status", "owner_note", "updated_at"])
        return instance


class SeekerDormRoomImageSerializer(serializers.ModelSerializer):
    """Expose dorm room images for seekers."""

    image = AbsoluteURLImageField(read_only=True)

    class Meta:
        model = DormRoomImage
        fields = ("id", "image", "caption")
        read_only_fields = fields


class SeekerDormRoomSerializer(serializers.ModelSerializer):
    """List dorm rooms in a seeker-friendly shape."""

    images = SeekerDormRoomImageSerializer(many=True, read_only=True)
    description = serializers.SerializerMethodField()

    class Meta:
        model = DormRoom
        fields = (
            "id",
            "name",
            "room_type",
            "capacity",
            "price_per_month",
            "total_units",
            "available_units",
            "is_available",
            "description",
            "images",
        )
        read_only_fields = fields

    def get_description(self, obj: DormRoom) -> str:
        """Return the optional description if the attribute exists."""

        return getattr(obj, "description", "") or ""


class SeekerDormImageSerializer(serializers.ModelSerializer):
    """Expose dorm gallery images for seekers."""

    image = AbsoluteURLImageField(read_only=True)

    class Meta:
        model = DormImage
        fields = ("id", "image", "caption")
        read_only_fields = fields


class SeekerDormSerializer(serializers.ModelSerializer):
    """Public representation of a dorm for seekers."""

    rooms = SeekerDormRoomSerializer(many=True, read_only=True)
    images = SeekerDormImageSerializer(many=True, read_only=True)
    cover_photo = serializers.SerializerMethodField()
    property_detail = serializers.SerializerMethodField()
    has_room_service = serializers.BooleanField(source="room_service_available", read_only=True)
    has_electricity = serializers.BooleanField(source="electricity_included", read_only=True)
    has_water = serializers.BooleanField(source="water_included", read_only=True)
    has_internet = serializers.BooleanField(source="internet_included", read_only=True)

    class Meta:
        model = Dorm
        fields = (
            "id",
            "name",
            "description",
            "cover_photo",
            "amenities",
            "has_room_service",
            "has_electricity",
            "has_water",
            "has_internet",
            "is_active",
            "property_detail",
            "rooms",
            "images",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_cover_photo(self, obj: Dorm) -> str:
        request = self.context.get("request")
        if obj.cover_image:
            if request is not None:
                return request.build_absolute_uri(obj.cover_image.url)
            return obj.cover_image.url
        return ""

    def get_property_detail(self, obj: Dorm) -> dict[str, Any]:
        property_obj = obj.property
        return {
            "id": property_obj.id,
            "name": property_obj.name,
            "location": property_obj.location,
        }


class SeekerBookingRequestSerializer(serializers.ModelSerializer):
    """Serializer for seeker booking request listings."""

    dorm_summary = serializers.SerializerMethodField()
    room_summary = serializers.SerializerMethodField()
    check_in = serializers.DateField(source="move_in_date", allow_null=True, required=False)
    check_out = serializers.DateField(source="move_out_date", allow_null=True, required=False)

    class Meta:
        model = BookingRequest
        fields = (
            "id",
            "status",
            "owner_note",
            "check_in",
            "check_out",
            "created_at",
            "responded_at",
            "dorm_summary",
            "room_summary",
        )
        read_only_fields = fields

    def get_dorm_summary(self, obj: BookingRequest) -> Optional[dict[str, Any]]:
        dorm = getattr(obj.room, "dorm", None)
        if dorm is None:
            return None
        property_obj = dorm.property
        request = self.context.get("request")
        cover_photo = ""
        if dorm.cover_image:
            if request is not None:
                cover_photo = request.build_absolute_uri(dorm.cover_image.url)
            else:
                cover_photo = dorm.cover_image.url
        return {
            "id": dorm.id,
            "name": dorm.name,
            "property_name": property_obj.name,
            "property_location": property_obj.location,
            "cover_photo": cover_photo,
        }

    def get_room_summary(self, obj: BookingRequest) -> Optional[dict[str, Any]]:
        room = getattr(obj, "room", None)
        if room is None:
            return None
        return {
            "id": room.id,
            "name": room.name,
            "room_type": room.room_type,
        }


class SeekerBookingRequestCreateSerializer(serializers.ModelSerializer):
    """Handle seeker-initiated booking requests."""

    dorm = serializers.PrimaryKeyRelatedField(queryset=Dorm.objects.filter(is_active=True), write_only=True)
    room = serializers.PrimaryKeyRelatedField(queryset=DormRoom.objects.all())
    check_in = serializers.DateField(source="move_in_date", required=False, allow_null=True)
    check_out = serializers.DateField(source="move_out_date", required=False, allow_null=True)

    class Meta:
        model = BookingRequest
        fields = (
            "id",
            "dorm",
            "room",
            "seeker_name",
            "seeker_email",
            "seeker_phone",
            "message",
            "check_in",
            "check_out",
        )
        read_only_fields = ("id",)
        extra_kwargs = {
            "seeker_name": {"required": False, "allow_blank": True},
            "seeker_email": {"required": False, "allow_blank": True},
            "seeker_phone": {"required": False, "allow_blank": True},
            "message": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        dorm: Dorm = attrs.get("dorm")
        room: DormRoom = attrs.get("room")
        check_in = attrs.get("move_in_date")
        check_out = attrs.get("move_out_date")

        if room and dorm and room.dorm_id != dorm.id:
            raise serializers.ValidationError({"room": _("Selected room does not belong to this dorm.")})

        if check_in and check_out and check_in > check_out:
            raise serializers.ValidationError({"check_out": _("Check-out date must be after check-in date.")})

        if room and not room.is_available:
            raise serializers.ValidationError({"room": _("This room is not currently accepting bookings.")})

        if room and room.available_units is not None and room.available_units <= 0:
            raise serializers.ValidationError({"room": _("This room is fully booked at the moment.")})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> BookingRequest:
        validated_data.pop("dorm", None)
        validated_data.setdefault("status", BookingRequest.Status.PENDING)
        return super().create(validated_data)
