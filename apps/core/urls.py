"""Core app URL configuration."""
from __future__ import annotations

from django.urls import path

from .views import HomeView

app_name = "core"

urlpatterns = [
    path("home/", HomeView.as_view(), name="home"),
]
