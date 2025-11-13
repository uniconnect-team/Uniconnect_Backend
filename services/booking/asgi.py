"""ASGI config for the booking service."""
from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "services.booking.settings")

application = get_asgi_application()
