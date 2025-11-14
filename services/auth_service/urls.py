"""URL configuration for the authentication microservice."""
from __future__ import annotations

from django.urls import include, path

from apps.users.views import LoginView, OwnerRegisterView, RegisterView

app_name = "auth_service"

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/register/", RegisterView.as_view(), name="register"),
    path("api/v1/auth/register-owner/", OwnerRegisterView.as_view(), name="register-owner"),
    path("api/v1/auth/login/", LoginView.as_view(), name="login"),
]
