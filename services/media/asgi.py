"""ASGI config for the media service."""
from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "services.media.settings")

application = get_asgi_application()
