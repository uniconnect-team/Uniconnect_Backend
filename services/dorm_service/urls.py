"""URL configuration for the dorm management microservice."""
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.users.views import (
    OwnerDormImageViewSet,
    OwnerDormRoomImageViewSet,
    OwnerDormRoomViewSet,
    OwnerDormViewSet,
    SeekerDormViewSet,
)

app_name = "dorm_service"

router = DefaultRouter()
router.register(r"owner/dorms", OwnerDormViewSet, basename="owner-dorms")
router.register(r"owner/dorm-rooms", OwnerDormRoomViewSet, basename="owner-dorm-rooms")
router.register(r"owner/dorm-images", OwnerDormImageViewSet, basename="owner-dorm-images")
router.register(
    r"owner/dorm-room-images",
    OwnerDormRoomImageViewSet,
    basename="owner-dorm-room-images",
)
router.register(r"seeker/dorms", SeekerDormViewSet, basename="seeker-dorms")

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/users/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)