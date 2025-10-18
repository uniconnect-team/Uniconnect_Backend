"""uniconnect URL Configuration."""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.users.views import VerifyEmailPageView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.users.urls")),
    path("verify-email/", VerifyEmailPageView.as_view(), name="verify-email-page"),
]
