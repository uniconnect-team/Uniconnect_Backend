"""Media service Django settings."""
from __future__ import annotations

import os
from pathlib import Path

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
    "services.media",
    "services.authentication.users",
]

ROOT_URLCONF = "services.media.urls"
WSGI_APPLICATION = "services.media.wsgi.application"
ASGI_APPLICATION = "services.media.asgi.application"

BASE_DIR = Path(__file__).resolve().parent

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEBUG = True
