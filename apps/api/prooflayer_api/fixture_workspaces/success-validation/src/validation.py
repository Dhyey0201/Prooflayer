"""Username validation for the signup endpoint."""


def validate_username(username: str) -> bool:
    # BUG: accepts any non-empty string.
    return bool(username)
