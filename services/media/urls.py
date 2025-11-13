"""URL configuration for the media service."""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from services.authentication.users.views import (
    OwnerDormImageViewSet,
    OwnerDormRoomImageViewSet,
)


def health_check(_request):
    return JsonResponse({"status": "ok"})


media_router = DefaultRouter()
media_router.register(
    r"owner/dorm-images",
    OwnerDormImageViewSet,
    basename="owner-dorm-images",
)
media_router.register(
    r"owner/dorm-room-images",
    OwnerDormRoomImageViewSet,
    basename="owner-dorm-room-images",
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("media/", include((media_router.urls, "media"), namespace="media")),
]
