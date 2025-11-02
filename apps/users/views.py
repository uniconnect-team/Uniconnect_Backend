"""Views for the users app."""
from __future__ import annotations

from typing import Any

from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile, Property
from .serializers import (
    LoginSerializer,
    MeSerializer,
    OwnerRegisterSerializer,
    PropertySerializer,
    RegisterSerializer,
)


class RegisterView(APIView):
    """Handle user registration requests."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):  # noqa: D401 - simple wrapper
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
    """Handle dorm owner registration with property details."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):  # noqa: D401 - simple wrapper
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


class MeView(generics.RetrieveAPIView):
    """Return the authenticated user's profile information."""

    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get_object(self):  # type: ignore[override]
        return self.request.user


class PropertyViewSet(viewsets.ModelViewSet):
    """CRUD operations for dorm owner properties."""

    serializer_class = PropertySerializer
    permission_classes = [IsAuthenticated]

    def _require_owner_profile(self) -> Profile:
        profile = getattr(self.request.user, "profile", None)
        if not profile or profile.role != Profile.Roles.OWNER:
            raise PermissionDenied("Only dorm owners can manage properties.")
        return profile

    def get_queryset(self):  # type: ignore[override]
        profile = getattr(self.request.user, "profile", None)
        if not profile or profile.role != Profile.Roles.OWNER:
            return Property.objects.none()
        return (
            Property.objects.filter(owner=profile)
            .select_related("owner")
            .prefetch_related("rooms", "images")
            .order_by("name")
        )

    def get_serializer_context(self) -> dict[str, Any]:  # type: ignore[override]
        context = super().get_serializer_context()
        profile = getattr(self.request.user, "profile", None)
        if profile and profile.role == Profile.Roles.OWNER:
            context["owner"] = profile
        return context

    def perform_create(self, serializer):  # type: ignore[override]
        self._require_owner_profile()
        serializer.save()

    def perform_update(self, serializer):  # type: ignore[override]
        self._require_owner_profile()
        serializer.save()

    def list(self, request, *args, **kwargs):  # type: ignore[override]
        self._require_owner_profile()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):  # type: ignore[override]
        self._require_owner_profile()
        return super().retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):  # type: ignore[override]
        self._require_owner_profile()
        return super().destroy(request, *args, **kwargs)
