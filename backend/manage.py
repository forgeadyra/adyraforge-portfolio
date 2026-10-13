#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path


def main() -> None:
    dotenv = Path(__file__).resolve().parent / ".env"
    if dotenv.is_file():
        # Local convenience only. Real environment variables always win.
        import environ

        environ.Env.read_env(dotenv)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
