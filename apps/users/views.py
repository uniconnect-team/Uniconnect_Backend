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
    VerifyEmailConfirmSerializer,
    VerifyEmailRequestSerializer,
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
    """Trigger a new verification email for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = VerifyEmailRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                "ok": True,
                "cooldownSeconds": result["cooldown_seconds"],
                "expiresAt": result["expires_at"].isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class VerifyEmailConfirmView(APIView):
    """Confirm a verification token received by email."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = VerifyEmailConfirmSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"ok": True}, status=status.HTTP_200_OK)


class VerifyEmailPageView(TemplateView):
    """Render a minimal verification UI for entering the OTP code."""

    template_name = "users/verify_email.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        context.setdefault("page_title", "Verify your student email")
        context.setdefault("support_email", getattr(settings, "MAIL_FROM", "support@uniconnect"))
        return context
