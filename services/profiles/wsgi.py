"""WSGI config for the profiles service."""
from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "services.profiles.settings")

application = get_wsgi_application()
