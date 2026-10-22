from src.auth import Token, is_expired, refresh


def test_token_expires_at_expiry_instant() -> None:
    assert is_expired(Token("t", expires_at=100), now=100)


def test_refresh_replaces_token_at_expiry_instant() -> None:
    token = Token("t", expires_at=100)
    assert refresh(token, now=100).expires_at == 400
