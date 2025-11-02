"""Views for the users app."""
from __future__ import annotations

from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile, Property, PropertyImage, Room, RoomImage
from .serializers import (
    LoginSerializer,
    MeSerializer,
    OwnerProfileCompletionSerializer,
    OwnerRegisterSerializer,
    PropertyImageSerializer,
    PropertySerializer,
    RegisterSerializer,
    RoomImageSerializer,
    RoomSerializer,
    SeekerProfileCompletionSerializer,
    _build_user_payload,
)


class IsOwnerUser(IsAuthenticated):
    """Ensure the authenticated user is a dorm owner."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        profile = getattr(request.user, "profile", None)
        return bool(profile and profile.role == Profile.Roles.OWNER)


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


class OwnerPropertyViewSet(viewsets.ModelViewSet):
    """CRUD operations for owner-managed properties."""

    serializer_class = PropertySerializer
    permission_classes = [IsOwnerUser]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = (
            Property.objects.filter(owner=profile)
            .prefetch_related("images", "rooms", "rooms__images")
            .order_by("name")
        )
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["owner"] = self.request.user.profile
        return context

    def perform_destroy(self, instance: Property) -> None:  # pragma: no cover - simple call
        if instance.owner != self.request.user.profile:
            raise PermissionDenied("You can only delete your own properties.")
        instance.delete()


class OwnerRoomViewSet(viewsets.ModelViewSet):
    """Manage rooms for owner properties."""

    serializer_class = RoomSerializer
    permission_classes = [IsOwnerUser]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = Room.objects.filter(property__owner=profile).prefetch_related("images")
        property_id = self.request.query_params.get("property")
        if property_id:
            queryset = queryset.filter(property_id=property_id)
        return queryset.order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["owner"] = self.request.user.profile
        return context

    def perform_destroy(self, instance: Room) -> None:  # pragma: no cover - simple call
        if instance.property.owner != self.request.user.profile:
            raise PermissionDenied("You can only delete your own rooms.")
        instance.delete()


class OwnerPropertyImageViewSet(viewsets.ModelViewSet):
    """Upload and manage property gallery images."""

    serializer_class = PropertyImageSerializer
    permission_classes = [IsOwnerUser]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = PropertyImage.objects.filter(property__owner=profile).order_by("-uploaded_at")
        property_id = self.request.query_params.get("property")
        if property_id:
            queryset = queryset.filter(property_id=property_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["owner"] = self.request.user.profile
        return context

    def perform_destroy(self, instance: PropertyImage) -> None:  # pragma: no cover - simple call
        if instance.property.owner != self.request.user.profile:
            raise PermissionDenied("You can only delete your own property images.")
        instance.delete()


class OwnerRoomImageViewSet(viewsets.ModelViewSet):
    """Upload and manage images for individual rooms."""

    serializer_class = RoomImageSerializer
    permission_classes = [IsOwnerUser]

    def get_queryset(self):
        profile = self.request.user.profile
        queryset = RoomImage.objects.filter(room__property__owner=profile).order_by("-uploaded_at")
        room_id = self.request.query_params.get("room")
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["owner"] = self.request.user.profile
        return context

    def perform_destroy(self, instance: RoomImage) -> None:  # pragma: no cover - simple call
        if instance.room.property.owner != self.request.user.profile:
            raise PermissionDenied("You can only delete your own room images.")
        instance.delete()
