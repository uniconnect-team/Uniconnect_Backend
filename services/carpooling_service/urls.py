from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.users.views import CarpoolRideViewSet

router = DefaultRouter()
router.register(r"rides", CarpoolRideViewSet, basename="carpool-rides")

urlpatterns = [
    path("api/v1/carpooling/", include(router.urls)),
]
