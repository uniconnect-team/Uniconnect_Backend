"""URL configuration for the notifications service."""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from services.notifications.views import BookingNotificationViewSet


def health_check(_request):
    return JsonResponse({"status": "ok"})


notifications_router = DefaultRouter()
notifications_router.register(
    r"seeker/notifications",
    BookingNotificationViewSet,
    basename="seeker-notifications",
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path(
        "notifications/",
        include((notifications_router.urls, "notifications"), namespace="notifications"),
    ),
]
