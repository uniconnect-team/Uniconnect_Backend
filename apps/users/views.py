"""Views for the users app."""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action


from .models import BookingRequest, Dorm, DormImage, DormRoom, DormRoomImage, Profile
from .serializers import (
    BookingRequestSerializer,
    DormImageSerializer,
    DormRoomImageSerializer,
    DormRoomSerializer,
    DormSerializer,
    LoginSerializer,
    MeSerializer,
    OwnerProfileCompletionSerializer,
    OwnerRegisterSerializer,
    RegisterSerializer,
    RoommateMatchSerializer,
    RoommateProfileSerializer,
    RoommateRequestSerializer,
    SeekerBookingRequestCreateSerializer,
    SeekerBookingRequestSerializer,
    SeekerDormSerializer,
    SeekerProfileCompletionSerializer,
    _build_user_payload,
    RoommateProfile,      
    RoommateMatch,        
    RoommateRequest, 
)


class RegisterView(APIView):
    """Handle user registration requests."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(
            data=request.data,
            context={
                "request": request,
                "ip": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class OwnerRegisterView(APIView):
    """Handle dorm owner registration."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OwnerRegisterSerializer(
            data=request.data,
            context={
                "request": request,
                "ip": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Handle authentication via email or phone."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class CompleteProfileView(APIView):
    """Handle profile completion for authenticated users."""
    
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        profile = getattr(self.request.user, 'profile', None)
        if not profile:
            return SeekerProfileCompletionSerializer
        
        if profile.role == Profile.Roles.SEEKER:
            return SeekerProfileCompletionSerializer
        elif profile.role == Profile.Roles.OWNER:
            return OwnerProfileCompletionSerializer
        
        return SeekerProfileCompletionSerializer
    
    def post(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(
            data=request.data,
            context={'user': request.user, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.update_profile(request.user, serializer.validated_data)
        
        # Return updated user data
        return Response(
            _build_user_payload(request.user),
            status=status.HTTP_200_OK
        )


class MeView(generics.RetrieveAPIView):
    """Return the authenticated user's profile information."""

    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


class IsOwnerProfile(BasePermission):
    """Ensure the authenticated user is a dorm owner."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, "profile", None)
        return bool(profile and profile.role == Profile.Roles.OWNER)


class IsSeekerProfile(BasePermission):
    """Ensure the authenticated user is a seeker."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, "profile", None)
        return bool(profile and profile.role == Profile.Roles.SEEKER)


class OwnerDormViewSet(viewsets.ModelViewSet):
    """CRUD endpoints for dorm management by owners."""

    serializer_class = DormSerializer
    permission_classes = [IsAuthenticated, IsOwnerProfile]

    def get_queryset(self):
        profile = self.request.user.profile
        return (
            Dorm.objects.filter(property__owner=profile)
            .select_related("property")
            .prefetch_related("rooms", "images")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class OwnerDormRoomViewSet(viewsets.ModelViewSet):
    """Manage dorm rooms for an owner's dorms."""

    serializer_class = DormRoomSerializer
    permission_classes = [IsAuthenticated, IsOwnerProfile]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = DormRoom.objects.filter(dorm__property__owner=profile).select_related("dorm")
        dorm_id = self.request.query_params.get("dorm")
        if dorm_id:
            queryset = queryset.filter(dorm_id=dorm_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class OwnerDormImageViewSet(viewsets.ModelViewSet):
    """Manage dorm gallery images."""

    serializer_class = DormImageSerializer
    permission_classes = [IsAuthenticated, IsOwnerProfile]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = DormImage.objects.filter(dorm__property__owner=profile).select_related("dorm")
        dorm_id = self.request.query_params.get("dorm")
        if dorm_id:
            queryset = queryset.filter(dorm_id=dorm_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class OwnerDormRoomImageViewSet(viewsets.ModelViewSet):
    """Manage room gallery images for an owner's dorm rooms."""

    serializer_class = DormRoomImageSerializer
    permission_classes = [IsAuthenticated, IsOwnerProfile]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = DormRoomImage.objects.filter(room__dorm__property__owner=profile).select_related(
            "room",
            "room__dorm",
        )
        room_id = self.request.query_params.get("room")
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class OwnerBookingRequestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Allow owners to review and respond to booking requests."""

    serializer_class = BookingRequestSerializer
    permission_classes = [IsAuthenticated, IsOwnerProfile]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = (
            BookingRequest.objects.filter(room__dorm__property__owner=profile)
            .select_related("room", "room__dorm", "room__dorm__property")
        )
        status_filter = self.request.query_params.get("status")
        dorm_id = self.request.query_params.get("dorm")
        room_id = self.request.query_params.get("room")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if dorm_id:
            queryset = queryset.filter(room__dorm_id=dorm_id)
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        instance = serializer.save()
        if (
            instance.status != BookingRequest.Status.PENDING
            and not instance.responded_at
        ):
            instance.responded_at = timezone.now()
            instance.save(update_fields=["responded_at", "updated_at"])


class SeekerDormViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Allow seekers to browse published dorms."""

    serializer_class = SeekerDormSerializer
    permission_classes = [IsAuthenticated, IsSeekerProfile]

    def get_queryset(self):
        queryset = (
            Dorm.objects.all()
            .select_related("property", "property__owner")
            .prefetch_related("rooms", "rooms__images", "images")
        )

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            value = is_active.lower()
            if value in {"true", "1"}:
                queryset = queryset.filter(is_active=True)
            elif value in {"false", "0"}:
                queryset = queryset.filter(is_active=False)
        else:
            queryset = queryset.filter(is_active=True)

        property_id = self.request.query_params.get("property")
        if property_id:
            queryset = queryset.filter(property_id=property_id)

        return queryset.order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class SeekerBookingRequestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Allow seekers to create and track booking requests."""

    permission_classes = [IsAuthenticated, IsSeekerProfile]

    def get_queryset(self):
        user = self.request.user
        filters = Q(seeker_email=user.email)
        profile = getattr(user, "profile", None)
        if profile and profile.phone:
            filters |= Q(seeker_phone=profile.phone)

        queryset = (
            BookingRequest.objects.filter(filters)
            .select_related("room", "room__dorm", "room__dorm__property")
            .order_by("-created_at")
        )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        dorm_id = self.request.query_params.get("dorm")
        if dorm_id:
            queryset = queryset.filter(room__dorm_id=dorm_id)

        room_id = self.request.query_params.get("room")
        if room_id:
            queryset = queryset.filter(room_id=room_id)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return SeekerBookingRequestCreateSerializer
        return SeekerBookingRequestSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = SeekerBookingRequestSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        user = self.request.user
        profile = getattr(user, "profile", None)
        defaults = {
            "seeker_name": serializer.validated_data.get("seeker_name") or getattr(profile, "full_name", ""),
            "seeker_email": serializer.validated_data.get("seeker_email") or user.email,
            "seeker_phone": serializer.validated_data.get("seeker_phone") or getattr(profile, "phone", ""),
        }
        serializer.save(**defaults)


class NotificationListView(APIView):
    """Return lightweight notifications for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = getattr(user, "profile", None)
        notifications: list[dict[str, object]] = []

        if profile and profile.role == Profile.Roles.OWNER:
            pending_requests = (
                BookingRequest.objects.filter(room__dorm__property__owner=profile)
                .select_related("room", "room__dorm")
                .order_by("-created_at")[:20]
            )
            for booking in pending_requests:
                if booking.status == BookingRequest.Status.PENDING:
                    notifications.append(
                        {
                            "id": booking.id,
                            "type": "BOOKING_PENDING",
                            "message": (
                                f"New booking request for {booking.room.name} in "
                                f"{booking.room.dorm.name}."
                            ),
                            "status": booking.status,
                            "created_at": booking.created_at.isoformat(),
                        }
                    )
                else:
                    notifications.append(
                        {
                            "id": booking.id,
                            "type": "BOOKING_UPDATE",
                            "message": (
                                f"Booking request for {booking.room.name} in "
                                f"{booking.room.dorm.name} is {booking.status}."
                            ),
                            "status": booking.status,
                            "created_at": booking.updated_at.isoformat(),
                        }
                    )
        elif profile and profile.role == Profile.Roles.SEEKER:
            filters = Q(seeker_email=user.email)
            if profile.phone:
                filters |= Q(seeker_phone=profile.phone)

            seeker_requests = (
                BookingRequest.objects.filter(filters)
                .select_related("room", "room__dorm")
                .order_by("-updated_at")[:20]
            )
            for booking in seeker_requests:
                notifications.append(
                    {
                        "id": booking.id,
                        "type": "BOOKING_STATUS",
                        "message": (
                            f"Your booking for {booking.room.name} in {booking.room.dorm.name} "
                            f"is {booking.status}."
                        ),
                        "status": booking.status,
                        "created_at": booking.updated_at.isoformat(),
                    }
                )

        return Response({
            "count": len(notifications),
            "results": notifications,
        })

class RoommateProfileViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Manage the authenticated user's roommate profile."""
    
    serializer_class = RoommateProfileSerializer
    permission_classes = [IsAuthenticated, IsSeekerProfile]
    
    def get_queryset(self):
        """Return only the authenticated user's profile."""
        return RoommateProfile.objects.filter(profile=self.request.user.profile)
    
    def get_object(self):
        """Get or create the roommate profile for the authenticated user."""
        profile = self.request.user.profile
        roommate_profile, created = RoommateProfile.objects.get_or_create(profile=profile)
        return roommate_profile
    
    def retrieve(self, request, *args, **kwargs):
        """Get the authenticated user's roommate profile."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """Update the authenticated user's roommate profile."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class RoommateMatchViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Browse potential roommate matches."""
    
    serializer_class = RoommateMatchSerializer
    permission_classes = [IsAuthenticated, IsSeekerProfile]
    
    def get_queryset(self):
        """Return matches for the authenticated user, ordered by compatibility."""
        profile = self.request.user.profile
        
        # Get filter parameters
        min_score = self.request.query_params.get("min_score", 50)
        favorited_only = self.request.query_params.get("favorited", "").lower() == "true"
        
        queryset = RoommateMatch.objects.filter(seeker=profile)
        
        if min_score:
            try:
                queryset = queryset.filter(compatibility_score__gte=int(min_score))
            except ValueError:
                pass
        
        if favorited_only:
            queryset = queryset.filter(is_favorited=True)
        
        return queryset.select_related("match", "match__user", "match__roommate_profile")
    
    def list(self, request, *args, **kwargs):
        """
        List roommate matches for the authenticated user.
        Automatically generates matches if none exist.
        """
        profile = request.user.profile
        
        # Ensure user has a roommate profile
        try:
            my_roommate_profile = profile.roommate_profile
        except RoommateProfile.DoesNotExist:
            return Response(
                {"detail": "Please create your roommate profile first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Check if matches need to be generated
        existing_matches = RoommateMatch.objects.filter(seeker=profile).count()
        
        if existing_matches == 0:
            # Generate matches
            self._generate_matches(profile, my_roommate_profile)
        
        return super().list(request, *args, **kwargs)
    
    def _generate_matches(self, seeker_profile: Profile, seeker_roommate_profile: RoommateProfile):
        """Generate compatibility matches for a seeker."""
        # Find all other active roommate profiles (excluding self)
        other_profiles = RoommateProfile.objects.filter(
            is_active=True,
            profile__role=Profile.Roles.SEEKER,
        ).exclude(profile=seeker_profile).select_related("profile", "profile__user")
        
        matches_to_create = []
        
        for other_roommate_profile in other_profiles:
            # Calculate compatibility
            score = seeker_roommate_profile.calculate_compatibility(other_roommate_profile)
            
            # Only create match if score is above threshold (e.g., 25%)
            if score >= 25:
                matches_to_create.append(
                    RoommateMatch(
                        seeker=seeker_profile,
                        match=other_roommate_profile.profile,
                        compatibility_score=score,
                    )
                )
        
        # Bulk create matches
        RoommateMatch.objects.bulk_create(matches_to_create, ignore_conflicts=True)
    
    @action(detail=True, methods=["post"])
    def toggle_favorite(self, request, pk=None):
        """Toggle favorite status for a match."""
        match = self.get_object()
        match.is_favorited = not match.is_favorited
        match.save(update_fields=["is_favorited", "updated_at"])
        serializer = self.get_serializer(match)
        return Response(serializer.data)
    
    @action(detail=True, methods=["post"])
    def mark_viewed(self, request, pk=None):
        """Mark a match as viewed."""
        match = self.get_object()
        if not match.is_viewed:
            match.is_viewed = True
            match.save(update_fields=["is_viewed", "updated_at"])
        serializer = self.get_serializer(match)
        return Response(serializer.data)
    
    @action(detail=False, methods=["post"])
    def refresh_matches(self, request):
        """Regenerate all matches for the authenticated user."""
        profile = request.user.profile
        
        try:
            my_roommate_profile = profile.roommate_profile
        except RoommateProfile.DoesNotExist:
            return Response(
                {"detail": "Please create your roommate profile first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Delete existing matches
        RoommateMatch.objects.filter(seeker=profile).delete()
        
        # Generate new matches
        self._generate_matches(profile, my_roommate_profile)
        
        return Response({"detail": "Matches refreshed successfully."})


class RoommateRequestViewSet(viewsets.ModelViewSet):
    """Send and manage roommate connection requests."""
    
    serializer_class = RoommateRequestSerializer
    permission_classes = [IsAuthenticated, IsSeekerProfile]
    
    def get_queryset(self):
        """Return requests sent by or to the authenticated user."""
        profile = self.request.user.profile
        
        # Filter: sent, received, or all
        filter_type = self.request.query_params.get("type", "all")
        status_filter = self.request.query_params.get("status")
        
        if filter_type == "sent":
            queryset = RoommateRequest.objects.filter(sender=profile)
        elif filter_type == "received":
            queryset = RoommateRequest.objects.filter(receiver=profile)
        else:
            queryset = RoommateRequest.objects.filter(
                Q(sender=profile) | Q(receiver=profile)
            )
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related("sender", "receiver", "sender__user", "receiver__user")
    
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Accept a received roommate request."""
        roommate_request = self.get_object()
        
        # Ensure user is the receiver
        if roommate_request.receiver != request.user.profile:
            return Response(
                {"detail": "You can only accept requests sent to you."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        if roommate_request.status != RoommateRequest.Status.PENDING:
            return Response(
                {"detail": "This request has already been responded to."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        roommate_request.status = RoommateRequest.Status.ACCEPTED
        roommate_request.response_message = request.data.get("response_message", "")
        roommate_request.responded_at = timezone.now()
        roommate_request.save()
        
        serializer = self.get_serializer(roommate_request)
        return Response(serializer.data)
    
    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        """Decline a received roommate request."""
        roommate_request = self.get_object()
        
        # Ensure user is the receiver
        if roommate_request.receiver != request.user.profile:
            return Response(
                {"detail": "You can only decline requests sent to you."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        if roommate_request.status != RoommateRequest.Status.PENDING:
            return Response(
                {"detail": "This request has already been responded to."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        roommate_request.status = RoommateRequest.Status.DECLINED
        roommate_request.response_message = request.data.get("response_message", "")
        roommate_request.responded_at = timezone.now()
        roommate_request.save()
        
        serializer = self.get_serializer(roommate_request)
        return Response(serializer.data)
    
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a sent roommate request."""
        roommate_request = self.get_object()
        
        # Ensure user is the sender
        if roommate_request.sender != request.user.profile:
            return Response(
                {"detail": "You can only cancel requests you sent."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        if roommate_request.status != RoommateRequest.Status.PENDING:
            return Response(
                {"detail": "Cannot cancel a request that has been responded to."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        roommate_request.status = RoommateRequest.Status.CANCELLED
        roommate_request.save()
        
        serializer = self.get_serializer(roommate_request)
        return Response(serializer.data)