"""Users app URL configuration."""
from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CompleteProfileView,
    LoginView,
    MeView,
    OwnerPropertyImageViewSet,
    OwnerPropertyViewSet,
    OwnerRegisterView,
    OwnerRoomImageViewSet,
    OwnerRoomViewSet,
    RegisterView,
)

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register-owner/", OwnerRegisterView.as_view(), name="register-owner"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
]


router = DefaultRouter()
router.register("owner/properties", OwnerPropertyViewSet, basename="owner-properties")
router.register("owner/rooms", OwnerRoomViewSet, basename="owner-rooms")
router.register(
    "owner/property-images",
    OwnerPropertyImageViewSet,
    basename="owner-property-images",
)
router.register(
    "owner/room-images",
    OwnerRoomImageViewSet,
    basename="owner-room-images",
)

urlpatterns += router.urls
