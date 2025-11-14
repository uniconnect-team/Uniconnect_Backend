"""URL configuration for the booking microservice."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.users.views import OwnerBookingRequestViewSet, SeekerBookingRequestViewSet

app_name = "booking_service"

router = DefaultRouter()
router.register(
    r"owner/booking-requests",
    OwnerBookingRequestViewSet,
    basename="owner-booking-requests",
)
router.register(
    r"seeker/booking-requests",
    SeekerBookingRequestViewSet,
    basename="seeker-booking-requests",
)

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/users/", include(router.urls)),
]
