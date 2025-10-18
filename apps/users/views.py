"""Views for the users app."""
from __future__ import annotations

from django.conf import settings
from django.views.generic import TemplateView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    LoginSerializer,
    MeSerializer,
    RegisterSerializer,
    VerificationConfirmSerializer,
    VerificationRequestSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Handle user registration."""

    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer


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


class VerifyEmailRequestView(APIView):
    """Initiate student email verification."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):  # noqa: D401 - simple wrapper
        serializer = VerificationRequestSerializer(
            data=request.data,
            context={
                "request": request,
                "ip": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class VerifyEmailConfirmView(APIView):
    """Confirm a student email verification code."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):  # noqa: D401 - simple wrapper
        serializer = VerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class VerifyEmailPageView(TemplateView):
    """Render the verification page shown after signup."""

    template_name = "users/verify_email.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "expiry_minutes": getattr(settings, "VERIFY_TOKEN_TTL_MIN", 15),
                "cooldown_seconds": getattr(settings, "VERIFY_RESEND_COOLDOWN_SEC", 60),
            }
        )
        return context
