"""Service utilities for the users app."""

from importlib import import_module
from typing import Any

__all__ = ["confirm_code", "send_verification"]


def _load_verification() -> Any:
    return import_module(".verification", __name__)


def send_verification(*args, **kwargs):
    """Proxy to :func:`verification.send_verification` with lazy import."""

    return _load_verification().send_verification(*args, **kwargs)


def confirm_code(*args, **kwargs):
    """Proxy to :func:`verification.confirm_code` with lazy import."""

    return _load_verification().confirm_code(*args, **kwargs)
