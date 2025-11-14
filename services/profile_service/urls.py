"""URL configuration for the profile microservice."""
from __future__ import annotations

from django.urls import include, path

from apps.users.views import CompleteProfileView, MeView

app_name = "profile_service"

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/users/me/", MeView.as_view(), name="me"),
    path("api/users/complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
]
