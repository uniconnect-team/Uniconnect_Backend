"""Users app URL configuration."""
from __future__ import annotations

from django.urls import path

from .views import (
    LoginView,
    MeView,
    RegisterView,
    VerifyEmailConfirmView,
    VerifyEmailPageView,
    VerifyEmailRequestView,
)

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("verify-email/", VerifyEmailPageView.as_view(), name="verify-email-page"),
    path("verify-email/request/", VerifyEmailRequestView.as_view(), name="verify-email-request"),
    path("verify-email/confirm/", VerifyEmailConfirmView.as_view(), name="verify-email-confirm"),
]
