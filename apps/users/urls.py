"""Users app URL configuration."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LoginView, MeView, OwnerRegisterView, PropertyViewSet, RegisterView

app_name = "users"

router = DefaultRouter()
router.register(r"properties", PropertyViewSet, basename="property")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register-owner/", OwnerRegisterView.as_view(), name="register-owner"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]
