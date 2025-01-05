import re
from django.core.exceptions import ValidationError


def is_hex_color(value: str) -> bool:
    """
    Checks if a string is a valid HEX color.
    Supports formats: #RGB, #RRGGBB.
    """
    pattern = r"^#(?:[0-9a-fA-F]{3}){1,2}$"
    return bool(re.match(pattern, value))


def validate_hex_color(value: str):
    """
    Django-compatible validator for HEX color codes.
    Raises ValidationError if the color is invalid.
    """
    if not is_hex_color(value):
        raise ValidationError("Invalid HEX color code.")
