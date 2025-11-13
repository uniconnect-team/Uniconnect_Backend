"""URL configuration for the booking service."""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from services.authentication.users.views import (
    OwnerBookingRequestViewSet,
    SeekerBookingRequestViewSet,
)


def health_check(_request):
    return JsonResponse({"status": "ok"})


booking_router = DefaultRouter()
booking_router.register(
    r"owner/booking-requests",
    OwnerBookingRequestViewSet,
    basename="owner-booking-requests",
)
booking_router.register(
    r"seeker/booking-requests",
    SeekerBookingRequestViewSet,
    basename="seeker-booking-requests",
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("booking/", include((booking_router.urls, "booking"), namespace="booking")),
]
