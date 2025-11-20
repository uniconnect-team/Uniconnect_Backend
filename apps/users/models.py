"""User app models."""
from __future__ import annotations

import hashlib

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class UniversityDomain(models.Model):
    """Allow-listed university email domains."""

    domain = models.CharField(max_length=255, unique=True)
    university_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]
        indexes = [models.Index(fields=["domain"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.domain


class Profile(models.Model):
    """Stores additional information for a Django user."""

    class Roles(models.TextChoices):
        SEEKER = "SEEKER", "SEEKER"
        OWNER = "OWNER", "OWNER"

    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=10, choices=Roles.choices)
    is_student_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    university_domain = models.ForeignKey(
        UniversityDomain,
        related_name="profiles",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)  # NEW FIELD
    profile_completed = models.BooleanField(default=False)  # NEW FIELD
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Profile({self.user.username})"


class EmailOTP(models.Model):
    """Stores email verification one-time passwords."""

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"EmailOTP(email={self.email}, created_at={self.created_at})"

    def is_expired(self) -> bool:
        """Return ``True`` when the OTP can no longer be used."""

        if self.expires_at <= timezone.now():
            return True
        if self.used_at is not None:
            return True
        return False

    def verify(self, code: str) -> bool:
        """Check whether ``code`` matches the stored hash."""

        return hashlib.sha256(code.encode("utf-8")).hexdigest() == self.code_hash


class PendingRegistration(models.Model):
    """Persist pending registration attempts awaiting verification."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    password_hash = models.CharField(max_length=128)
    role = models.CharField(max_length=10, choices=Profile.Roles.choices)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    university_domain = models.ForeignKey(
        UniversityDomain,
        related_name="pending_registrations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"PendingRegistration({self.email})"


class Property(models.Model):
    """Housing property owned by a registered dorm owner."""

    owner = models.ForeignKey(
        Profile,
        related_name="properties",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["owner", "name"])]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Property(name={self.name}, owner={self.owner_id})"


def _dorm_cover_upload_path(instance: "Dorm", filename: str) -> str:
    """Return a deterministic upload path for dorm cover images."""

    owner_id = instance.property.owner_id if instance.property_id else "unassigned"
    return f"dorms/{owner_id}/covers/{filename}"


def _dorm_gallery_upload_path(instance: "DormImage", filename: str) -> str:
    """Return upload path for dorm gallery images."""

    owner_id = instance.dorm.property.owner_id if instance.dorm.property_id else "unassigned"
    return f"dorms/{owner_id}/gallery/{filename}"


def _room_gallery_upload_path(instance: "DormRoomImage", filename: str) -> str:
    """Return upload path for room gallery images."""

    owner_id = instance.room.dorm.property.owner_id if instance.room.dorm.property_id else "unassigned"
    return f"dorms/{owner_id}/rooms/{instance.room_id or 'unassigned'}/{filename}"


class Dorm(models.Model):
    """A dormitory offered by a property owner."""

    property = models.ForeignKey(
        Property,
        related_name="dorms",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to=_dorm_cover_upload_path, blank=True, null=True)
    amenities = models.JSONField(default=list, blank=True)
    room_service_available = models.BooleanField(default=False)
    electricity_included = models.BooleanField(default=True)
    water_included = models.BooleanField(default=True)
    internet_included = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["property", "name"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Dorm(name={self.name}, property={self.property_id})"


class DormImage(models.Model):
    """Gallery images for a dorm."""

    dorm = models.ForeignKey(
        Dorm,
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to=_dorm_gallery_upload_path)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"DormImage(dorm={self.dorm_id}, id={self.id})"


class DormRoom(models.Model):
    """A room configuration inside a dorm."""

    class RoomType(models.TextChoices):
        SINGLE = "SINGLE", "Single"
        DOUBLE = "DOUBLE", "Double"
        TRIPLE = "TRIPLE", "Triple"
        QUAD = "QUAD", "Quad"
        STUDIO = "STUDIO", "Studio"
        OTHER = "OTHER", "Other"

    dorm = models.ForeignKey(
        Dorm,
        related_name="rooms",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    room_type = models.CharField(max_length=20, choices=RoomType.choices)
    capacity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2)
    amenities = models.JSONField(default=list, blank=True)
    total_units = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    available_units = models.PositiveIntegerField(default=1)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["dorm", "room_type"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"DormRoom(name={self.name}, dorm={self.dorm_id})"

class CarpoolRide(models.Model):
    driver = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="carpool_rides")
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField()
    # NEW FIELDS
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    vehicle_model = models.CharField(max_length=255, blank=True)

    seats_available = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.origin} → {self.destination} by {self.driver.full_name}"

class CarpoolBooking(models.Model):
    ride = models.ForeignKey(
        CarpoolRide,
        on_delete=models.CASCADE,
        related_name="bookings"
    )
    rider = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="carpool_bookings"
    )
    booked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-booked_at"]
        unique_together = ("ride", "rider")  # prevent double booking

    def __str__(self):
        return f"{self.rider.full_name} booked {self.ride}"

class DormRoomImage(models.Model):
    """Gallery images for specific dorm rooms."""

    room = models.ForeignKey(
        DormRoom,
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to=_room_gallery_upload_path)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"DormRoomImage(room={self.room_id}, id={self.id})"


class BookingRequest(models.Model):
    """A booking request submitted for a dorm room."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DECLINED = "DECLINED", "Declined"
        CANCELLED = "CANCELLED", "Cancelled"

    room = models.ForeignKey(
        DormRoom,
        related_name="booking_requests",
        on_delete=models.CASCADE,
    )
    seeker_name = models.CharField(max_length=255)
    seeker_email = models.EmailField()
    seeker_phone = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    move_in_date = models.DateField(null=True, blank=True)
    move_out_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    owner_note = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room", "status"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"BookingRequest(room={self.room_id}, status={self.status})"
    
class RoommateProfile(models.Model):
    """Store a student's roommate preferences and personality traits."""
    
    class SleepSchedule(models.TextChoices):
        EARLY_BIRD = "EARLY_BIRD", "Early Bird (Sleep before 10 PM)"
        NIGHT_OWL = "NIGHT_OWL", "Night Owl (Sleep after midnight)"
        FLEXIBLE = "FLEXIBLE", "Flexible"
    
    class CleanlinessLevel(models.TextChoices):
        VERY_CLEAN = "VERY_CLEAN", "Very Clean"
        MODERATELY_CLEAN = "MODERATELY_CLEAN", "Moderately Clean"
        RELAXED = "RELAXED", "Relaxed"
    
    class SocialPreference(models.TextChoices):
        VERY_SOCIAL = "VERY_SOCIAL", "Very Social"
        MODERATELY_SOCIAL = "MODERATELY_SOCIAL", "Moderately Social"
        PREFER_QUIET = "PREFER_QUIET", "Prefer Quiet"
    
    class StudyHabits(models.TextChoices):
        LIBRARY = "LIBRARY", "Study at Library"
        DORM = "DORM", "Study in Dorm"
        BOTH = "BOTH", "Both"

    # Link to the user's profile
    profile = models.OneToOneField(
        Profile,
        related_name="roommate_profile",
        on_delete=models.CASCADE,
    )
    
    # Preferences
    sleep_schedule = models.CharField(
        max_length=20,
        choices=SleepSchedule.choices,
        default=SleepSchedule.FLEXIBLE,
    )
    cleanliness_level = models.CharField(
        max_length=20,
        choices=CleanlinessLevel.choices,
        default=CleanlinessLevel.MODERATELY_CLEAN,
    )
    social_preference = models.CharField(
        max_length=20,
        choices=SocialPreference.choices,
        default=SocialPreference.MODERATELY_SOCIAL,
    )
    study_habits = models.CharField(
        max_length=20,
        choices=StudyHabits.choices,
        default=StudyHabits.BOTH,
    )
    
    # Additional preferences (stored as text)
    interests = models.TextField(
        blank=True,
        help_text="Comma-separated hobbies/interests (e.g., sports, music, gaming)"
    )
    budget_range = models.CharField(
        max_length=100,
        blank=True,
        help_text="Monthly budget for accommodation"
    )
    
    # Profile visibility
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this profile is visible to other students"
    )
    bio = models.TextField(
        blank=True,
        max_length=500,
        help_text="Short bio about yourself"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["profile", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"RoommateProfile({self.profile.user.username})"
    
    def calculate_compatibility(self, other: "RoommateProfile") -> int:
        """
        Calculate compatibility score (0-100) with another roommate profile.
        
        Scoring breakdown:
        - Sleep schedule match: 30 points
        - Cleanliness level match: 30 points
        - Social preference match: 25 points
        - Study habits match: 15 points
        """
        score = 0
        
        # Sleep schedule compatibility (30 points)
        if self.sleep_schedule == other.sleep_schedule:
            score += 30
        elif self.sleep_schedule == "FLEXIBLE" or other.sleep_schedule == "FLEXIBLE":
            score += 18
        
        # Cleanliness level compatibility (30 points)
        cleanliness_order = ["RELAXED", "MODERATELY_CLEAN", "VERY_CLEAN"]
        try:
            self_clean = cleanliness_order.index(self.cleanliness_level)
            other_clean = cleanliness_order.index(other.cleanliness_level)
            diff = abs(self_clean - other_clean)
            if diff == 0:
                score += 30
            elif diff == 1:
                score += 18
        except ValueError:
            pass
        
        # Social preference compatibility (25 points)
        if self.social_preference == other.social_preference:
            score += 25
        elif self.social_preference == "MODERATELY_SOCIAL" or other.social_preference == "MODERATELY_SOCIAL":
            score += 13
        
        # Study habits compatibility (15 points)
        if self.study_habits == other.study_habits:
            score += 15
        elif self.study_habits == "BOTH" or other.study_habits == "BOTH":
            score += 10
        
        return min(score, 100)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["profile", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"RoommateProfile({self.profile.user.username})"
    
    def calculate_compatibility(self, other: "RoommateProfile") -> int:
        """
        Calculate compatibility score (0-100) with another roommate profile.
        
        Scoring breakdown:
        - Sleep schedule match: 30 points
        - Cleanliness level match: 30 points
        - Social preference match: 25 points
        - Study habits match: 15 points
        """
        score = 0
        
        # Sleep schedule compatibility (30 points)
        if self.sleep_schedule == other.sleep_schedule:
            score += 30
        elif self.sleep_schedule == "FLEXIBLE" or other.sleep_schedule == "FLEXIBLE":
            score += 18
        
        # Cleanliness level compatibility (30 points)
        cleanliness_order = ["RELAXED", "MODERATELY_CLEAN", "VERY_CLEAN"]
        try:
            self_clean = cleanliness_order.index(self.cleanliness_level)
            other_clean = cleanliness_order.index(other.cleanliness_level)
            diff = abs(self_clean - other_clean)
            if diff == 0:
                score += 30
            elif diff == 1:
                score += 18
        except ValueError:
            pass
        
        # Social preference compatibility (25 points)
        if self.social_preference == other.social_preference:
            score += 25
        elif self.social_preference == "MODERATELY_SOCIAL" or other.social_preference == "MODERATELY_SOCIAL":
            score += 13
        
        # Study habits compatibility (15 points)
        if self.study_habits == other.study_habits:
            score += 15
        elif self.study_habits == "BOTH" or other.study_habits == "BOTH":
            score += 10
        
        return min(score, 100)

class Meta:
    ordering = ["-created_at"]
    indexes = [
            models.Index(fields=["profile", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"RoommateProfile({self.profile.user.username})"
    
    # ADD THIS METHOD HERE
    def calculate_compatibility(self, other: "RoommateProfile") -> int:
        """
        Calculate compatibility score (0-100) with another roommate profile.
        
        Scoring breakdown:
        - Sleep schedule match: 25 points
        - Cleanliness level match: 25 points
        - Social preference match: 20 points
        - Study habits match: 15 points
        - Preferred gender match: 15 points
        """
        score = 0
        
        # Sleep schedule compatibility (25 points)
        if self.sleep_schedule == other.sleep_schedule:
            score += 25
        elif self.sleep_schedule == "FLEXIBLE" or other.sleep_schedule == "FLEXIBLE":
            score += 15
        
        # Cleanliness level compatibility (25 points)
        cleanliness_order = ["RELAXED", "MODERATELY_CLEAN", "VERY_CLEAN"]
        try:
            self_clean = cleanliness_order.index(self.cleanliness_level)
            other_clean = cleanliness_order.index(other.cleanliness_level)
            diff = abs(self_clean - other_clean)
            if diff == 0:
                score += 25
            elif diff == 1:
                score += 15
            # diff == 2: no points
        except ValueError:
            pass
        
        # Social preference compatibility (20 points)
        if self.social_preference == other.social_preference:
            score += 20
        elif self.social_preference == "MODERATELY_SOCIAL" or other.social_preference == "MODERATELY_SOCIAL":
            score += 10
        
        # Study habits compatibility (15 points)
        if self.study_habits == other.study_habits:
            score += 15
        elif self.study_habits == "BOTH" or other.study_habits == "BOTH":
            score += 10
        
        # Preferred gender compatibility (15 points)
        # Get actual genders from their profiles
        self_gender = self.profile.gender if hasattr(self.profile, 'gender') else None
        other_gender = other.profile.gender if hasattr(other.profile, 'gender') else None
        
        # Check if both users' gender preferences are compatible
        # If this user has a gender preference, check if other user matches it
        self_match = (
            not self.preferred_gender or 
            self.preferred_gender == "" or 
            self.preferred_gender == other_gender
        )
        
        # If other user has a gender preference, check if this user matches it
        other_match = (
            not other.preferred_gender or 
            other.preferred_gender == "" or 
            other.preferred_gender == self_gender
        )
        
        # Both preferences must be satisfied for points
        if self_match and other_match:
            score += 15
        
        return min(score, 100)       
    
def calculate_compatibility(self, other: "RoommateProfile") -> int:
    """
    Calculate compatibility score (0-100) with another roommate profile.
    
    Scoring breakdown:
    - Sleep schedule match: 25 points
    - Cleanliness level match: 25 points
    - Social preference match: 20 points
    - Study habits match: 15 points
    - Preferred gender match: 15 points
    """
    score = 0
    
    # Sleep schedule compatibility (25 points)
    if self.sleep_schedule == other.sleep_schedule:
        score += 25
    elif self.sleep_schedule == "FLEXIBLE" or other.sleep_schedule == "FLEXIBLE":
        score += 15
    
    # Cleanliness level compatibility (25 points)
    cleanliness_order = ["RELAXED", "MODERATELY_CLEAN", "VERY_CLEAN"]
    try:
        self_clean = cleanliness_order.index(self.cleanliness_level)
        other_clean = cleanliness_order.index(other.cleanliness_level)
        diff = abs(self_clean - other_clean)
        if diff == 0:
            score += 25
        elif diff == 1:
            score += 15
        # diff == 2: no points
    except ValueError:
        pass
    
    # Social preference compatibility (20 points)
    if self.social_preference == other.social_preference:
        score += 20
    elif self.social_preference == "MODERATELY_SOCIAL" or other.social_preference == "MODERATELY_SOCIAL":
        score += 10
    
    # Study habits compatibility (15 points)
    if self.study_habits == other.study_habits:
        score += 15
    elif self.study_habits == "BOTH" or other.study_habits == "BOTH":
        score += 10
    
    # Preferred gender compatibility (15 points)
    # Get actual genders from their profiles
    self_gender = self.profile.gender if hasattr(self.profile, 'gender') else None
    other_gender = other.profile.gender if hasattr(other.profile, 'gender') else None
    
    # Check if both users' gender preferences are compatible
    # If this user has a gender preference, check if other user matches it
    self_match = (
        not self.preferred_gender or 
        self.preferred_gender == "" or 
        self.preferred_gender == other_gender
    )
    
    # If other user has a gender preference, check if this user matches it
    other_match = (
        not other.preferred_gender or 
        other.preferred_gender == "" or 
        other.preferred_gender == self_gender
    )
    
    # Both preferences must be satisfied for points
    if self_match and other_match:
        score += 15
    
    return min(score, 100)

class RoommateMatch(models.Model):
    """Store calculated matches between students."""
    
    # The student who is viewing matches
    seeker = models.ForeignKey(
        Profile,
        related_name="roommate_matches_as_seeker",
        on_delete=models.CASCADE,
    )
    
    # The potential roommate
    match = models.ForeignKey(
        Profile,
        related_name="roommate_matches_as_match",
        on_delete=models.CASCADE,
    )
    
    # Compatibility score (0-100)
    compatibility_score = models.PositiveSmallIntegerField(default=0)
    
    # Whether the seeker has viewed this match
    is_viewed = models.BooleanField(default=False)
    
    # Whether the seeker has favorited this match
    is_favorited = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-compatibility_score", "-created_at"]
        unique_together = [["seeker", "match"]]
        indexes = [
            models.Index(fields=["seeker", "-compatibility_score"]),
            models.Index(fields=["seeker", "is_favorited"]),
        ]

    def __str__(self) -> str:
        return f"Match({self.seeker.user.username} → {self.match.user.username}): {self.compatibility_score}%"


class RoommateRequest(models.Model):
    """Handle connection requests between potential roommates."""
    
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"
        CANCELLED = "CANCELLED", "Cancelled"
    
    # Student who sent the request
    sender = models.ForeignKey(
        Profile,
        related_name="sent_roommate_requests",
        on_delete=models.CASCADE,
    )
    
    # Student who receives the request
    receiver = models.ForeignKey(
        Profile,
        related_name="received_roommate_requests",
        on_delete=models.CASCADE,
    )
    
    # Optional message from sender
    message = models.TextField(
        blank=True,
        max_length=500,
        help_text="Introduction message"
    )
    
    # Request status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    
    # Response from receiver (optional)
    response_message = models.TextField(
        blank=True,
        max_length=500,
    )
    
    # Timestamps
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [["sender", "receiver"]]
        indexes = [
            models.Index(fields=["sender", "status"]),
            models.Index(fields=["receiver", "status"]),
        ]

    def __str__(self) -> str:
        return f"Request({self.sender.user.username} → {self.receiver.user.username}): {self.status}"