"""URL configuration for the dorms service."""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from services.authentication.users.views import (
    OwnerDormRoomViewSet,
    OwnerDormViewSet,
    SeekerDormViewSet,
)


def health_check(_request):
    return JsonResponse({"status": "ok"})


dorm_router = DefaultRouter()
dorm_router.register(r"owner/dorms", OwnerDormViewSet, basename="owner-dorms")
dorm_router.register(
    r"owner/dorm-rooms",
    OwnerDormRoomViewSet,
    basename="owner-dorm-rooms",
)
dorm_router.register(r"seeker/dorms", SeekerDormViewSet, basename="seeker-dorms")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("dorms/", include((dorm_router.urls, "dorms"), namespace="dorms")),
]
