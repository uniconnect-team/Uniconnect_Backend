"""Compatibility package for the authentication service."""
from importlib import import_module
import sys

_module = import_module("services.authentication.users")

globals().update(vars(_module))
sys.modules[__name__] = _module
