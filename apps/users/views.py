"""Views for the users app."""
from __future__ import annotations

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile
from .serializers import (
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