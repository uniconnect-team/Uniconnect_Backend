"""Core app views."""
from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HomeView(APIView):
    """Return a simple health response for the home endpoint."""

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response({"ok": True})
