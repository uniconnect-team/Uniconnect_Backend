# uniconnect/urls.py
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),

    # Same URLConf included twice, but with distinct namespaces
    path("api/v1/auth/", include(("apps.users.urls", "users"), namespace="users_auth")),
    path("api/users/", include(("apps.users.urls", "users"), namespace="users_api")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
