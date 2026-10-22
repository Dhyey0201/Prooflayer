from src.auth import bearer_header


def test_strips_whitespace() -> None:
    assert bearer_header("  abc \n") == {"Authorization": "Bearer abc"}
