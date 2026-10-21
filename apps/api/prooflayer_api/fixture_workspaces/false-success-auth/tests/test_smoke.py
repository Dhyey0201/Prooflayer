from src.auth import Token, refresh


def test_refresh_keeps_fresh_token() -> None:
    token = Token("t", expires_at=100)
    assert refresh(token, now=10) is token
