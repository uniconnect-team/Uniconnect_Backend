"""URL configuration for the authentication service."""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from services.authentication.users.views import LoginView, OwnerRegisterView, RegisterView


def health_check(_request):
    return JsonResponse({"status": "ok"})


auth_patterns = ([
    path("register/", RegisterView.as_view(), name="register"),
    path("register-owner/", OwnerRegisterView.as_view(), name="register-owner"),
    path("login/", LoginView.as_view(), name="login"),
], "auth")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("auth/", include(auth_patterns, namespace="auth")),
]
