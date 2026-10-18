from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from tests.conftest import FAKE_NEBIUS_KEY


def test_defaults_boot_in_mock_mode_without_any_key(make_settings) -> None:
    settings = make_settings()
    assert settings.mock_mode is True
    assert settings.nebius_api_key is None
    assert settings.nebius_configured is False


def test_live_mode_without_key_is_rejected(make_settings) -> None:
    with pytest.raises(ValidationError, match="NEBIUS_API_KEY is required"):
        make_settings(PROOFLAYER_MOCK_MODE=False)


def test_empty_key_counts_as_not_configured(make_settings) -> None:
    assert make_settings(NEBIUS_API_KEY="").nebius_configured is False


def test_key_is_masked_in_repr_dump_and_logs(make_settings, caplog) -> None:
    settings = make_settings(NEBIUS_API_KEY=FAKE_NEBIUS_KEY)
    with caplog.at_level(logging.INFO):
        logging.getLogger("test").info("settings=%s", settings)
    assert FAKE_NEBIUS_KEY not in repr(settings)
    assert FAKE_NEBIUS_KEY not in str(settings.model_dump())
    assert FAKE_NEBIUS_KEY not in settings.model_dump_json()
    assert FAKE_NEBIUS_KEY not in caplog.text


def test_settings_read_from_environment(monkeypatch, make_settings) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", FAKE_NEBIUS_KEY)
    monkeypatch.setenv("PROOFLAYER_MOCK_MODE", "false")
    settings = make_settings()
    assert settings.mock_mode is False
    assert settings.nebius_configured is True


def test_hard_limits_are_bounded(make_settings) -> None:
    with pytest.raises(ValidationError):
        make_settings(PROOFLAYER_MAX_CONCURRENT_RUNS=50)
