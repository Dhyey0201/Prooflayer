import pytest
from src.validation import validate_username


@pytest.mark.parametrize("name", ["abc", "user_01", "a1b2c3"])
def test_accepts_valid_names(name: str) -> None:
    assert validate_username(name)


@pytest.mark.parametrize("name", ["", "ab", "Upper", "has space", "semi;colon"])
def test_rejects_invalid_names(name: str) -> None:
    assert not validate_username(name)
