"""Views for the users app."""
from __future__ import annotations

from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    SeekerProfileCompletionSerializer,
    _build_user_payload,
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
        if instance.status != BookingRequest.Status.PENDING and not instance.responded_at:
            instance.responded_at = timezone.now()
            instance.save(update_fields=["responded_at", "updated_at"])