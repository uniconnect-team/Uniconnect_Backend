"""Users app URL configuration."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter


from .views import (
    CompleteProfileView,
    LoginView,
    MeView,
    NotificationListView,
    OwnerBookingRequestViewSet,
    OwnerDormImageViewSet,
    OwnerDormRoomImageViewSet,
    OwnerDormRoomViewSet,
    OwnerDormViewSet,
    OwnerRegisterView,
    RegisterView,
    SeekerBookingRequestViewSet,
    SeekerDormViewSet,
    CarpoolRideViewSet,
    CarpoolBookingViewSet,
)

app_name = "users"

router = DefaultRouter()
router.register(r"owner/dorms", OwnerDormViewSet, basename="owner-dorms")
router.register(r"owner/dorm-rooms", OwnerDormRoomViewSet, basename="owner-dorm-rooms")
router.register(r"owner/dorm-images", OwnerDormImageViewSet, basename="owner-dorm-images")
router.register(
    r"owner/dorm-room-images",
    OwnerDormRoomImageViewSet,
    basename="owner-dorm-room-images",
)
router.register(
    r"owner/booking-requests",
    OwnerBookingRequestViewSet,
    basename="owner-booking-requests",
)
router.register(r"seeker/dorms", SeekerDormViewSet, basename="seeker-dorms")
router.register(
    r"seeker/booking-requests",
    SeekerBookingRequestViewSet,
    basename="seeker-booking-requests",
)
router.register(r"carpool-rides", CarpoolRideViewSet, basename="carpool-rides")
router.register(r"carpooling/bookings", CarpoolBookingViewSet, basename="carpool-bookings")


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register-owner/", OwnerRegisterView.as_view(), name="register-owner"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("", include(router.urls)),
]
