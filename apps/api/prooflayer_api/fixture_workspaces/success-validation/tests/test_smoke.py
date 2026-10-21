from src.validation import validate_username


def test_module_imports() -> None:
    assert callable(validate_username)
