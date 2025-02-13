#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SdelayDelo.settings")
    try:
        from django.core.management import execute_from_command_line
        from django.conf import settings
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    try:
        with open(settings.LOG_FILE, "a") as f:
            f.write(
                f"\n### STARTING {'TESTING' if settings.TESTING else "SERVER"} ###\n\n"
            )
        execute_from_command_line(sys.argv)
    finally:
        with open(settings.LOG_FILE, "a") as f:
            f.write(
                f"\n### ENDING {'TESTING' if settings.TESTING else "SERVER"} ###\n\n"
            )


if __name__ == "__main__":
    main()
