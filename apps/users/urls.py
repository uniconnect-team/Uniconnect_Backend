"""Users app URL configuration."""
from __future__ import annotations

from django.urls import path

from .views import LoginView,CompleteProfileView, MeView, OwnerRegisterView, RegisterView

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register-owner/", OwnerRegisterView.as_view(), name="register-owner"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
]
