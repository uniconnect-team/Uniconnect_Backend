"""URL configuration for the notification microservice."""
from __future__ import annotations

from django.urls import include, path

from apps.users.views import NotificationListView

app_name = "notification_service"

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/users/notifications/", NotificationListView.as_view(), name="notifications"),
]
