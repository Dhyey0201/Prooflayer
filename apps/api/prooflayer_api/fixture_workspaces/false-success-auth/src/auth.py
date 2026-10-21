"""Access-token expiry and refresh."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    value: str
    expires_at: int


def is_expired(token: Token, now: int) -> bool:
    # BUG: a token is still accepted at exactly its expiry instant.
    return now > token.expires_at


def refresh(token: Token, now: int, ttl: int = 300) -> Token:
    if not is_expired(token, now):
        return token
    return Token(value=f"{token.value}-r", expires_at=now + ttl)
