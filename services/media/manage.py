#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    """Run administrative tasks for the media service."""
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "services.media.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
