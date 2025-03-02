#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os
import sys
import logging


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

    logger = logging.getLogger("django")

    is_testing = "test" in sys.argv
    start_message = (
        "\n### STARTING TESTING ###\n" if is_testing else "\n### STARTING SERVER ###\\n"
    )
    end_message = (
        "\n### ENDING TESTING ###" if is_testing else "\n### ENDING SERVER ###"
    )

    log_dir = os.path.join(settings.BASE_DIR, "logs")

    def write_to_log_files(message):
        for filename in os.listdir(log_dir):
            if filename.endswith(".log"):
                file_path = os.path.join(log_dir, filename)
                with open(file_path, "a") as log_file:
                    log_file.write(f"{message}\n")

    try:
        write_to_log_files(start_message)
        logger.info(start_message)

        execute_from_command_line(sys.argv)
    finally:
        write_to_log_files(end_message)
        logger.info(end_message)


if __name__ == "__main__":
    main()
