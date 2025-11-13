"""Authentication service Django settings."""
from __future__ import annotations

from uniconnect.settings import *  # noqa: F401,F403

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "services.authentication.users",
]

ROOT_URLCONF = "services.authentication.urls"
WSGI_APPLICATION = "services.authentication.wsgi.application"
ASGI_APPLICATION = "services.authentication.asgi.application"
