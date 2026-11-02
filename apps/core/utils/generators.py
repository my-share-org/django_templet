from django.utils.crypto import get_random_string
from typing import List

# Character pools
NUMBERS = "0123456789"
CAPITALS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SMALLS = "abcdefghijklmnopqrstuvwxyz"
SPECIALS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

def random_string(
    length: int,
    allow_numbers: bool = True,
    allow_capital: bool = False,
    allow_small: bool = False,
    allow_special: bool = False,
) -> str:
    """
    Generate a cryptographically secure random string.

    Raises:
        ValueError: If no character set is enabled or length is invalid.
    """

    if length <= 0:
        raise ValueError("length must be a positive integer")

    allowed_chars = "".join(
        chars
        for condition, chars in (
            (allow_numbers, NUMBERS),
            (allow_capital, CAPITALS),
            (allow_small, SMALLS),
            (allow_special, SPECIALS),
        )
        if condition
    )

    if not allowed_chars:
        raise ValueError("At least one character set must be enabled")

    return get_random_string(length, allowed_chars)
