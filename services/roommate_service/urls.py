"""URL configuration for the roommate matching microservice."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.users.views import (
    RoommateMatchViewSet,
    RoommateProfileViewSet,
    RoommateRequestViewSet,
)

app_name = "roommate_service"

router = DefaultRouter()
router.register(r"profile", RoommateProfileViewSet, basename="roommate-profile")
router.register(r"matches", RoommateMatchViewSet, basename="roommate-matches")
router.register(r"requests", RoommateRequestViewSet, basename="roommate-requests")

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/roommate/", include(router.urls)),
]