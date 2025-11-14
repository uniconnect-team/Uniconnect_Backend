"""URL configuration for the media service."""
from __future__ import annotations

from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OwnerDormImageViewSet, OwnerDormRoomImageViewSet


def health_check(_request):
    return JsonResponse({"status": "ok"})


router = DefaultRouter()
router.register("owner/dorm-images", OwnerDormImageViewSet, basename="owner-dorm-images")
router.register(
    "owner/dorm-room-images",
    OwnerDormRoomImageViewSet,
    basename="owner-dorm-room-images",
)

urlpatterns = [
    path("health/", health_check),
    path("media/", include(router.urls)),
]
