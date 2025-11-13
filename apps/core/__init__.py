"""Compatibility package for the core service."""
from importlib import import_module
import sys

_module = import_module("services.core.core")

globals().update(vars(_module))
sys.modules[__name__] = _module
