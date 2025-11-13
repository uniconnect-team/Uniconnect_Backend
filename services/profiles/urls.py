"""URL configuration for the profiles service."""
from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from services.authentication.users.views import CompleteProfileView, MeView


def health_check(_request):
    return JsonResponse({"status": "ok"})


profile_patterns = ([
    path("me/", MeView.as_view(), name="me"),
    path("complete/", CompleteProfileView.as_view(), name="complete"),
], "profiles")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("profiles/", include(profile_patterns, namespace="profiles")),
]
