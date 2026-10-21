from src.auth import bearer_header


def test_header_shape() -> None:
    assert bearer_header("abc") == {"Authorization": "Bearer abc"}
