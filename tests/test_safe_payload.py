from __future__ import annotations

import pytest

from prooflayer_api.enums import EventType
from prooflayer_api.evidence.safe_payload import (
    MAX_STRING_LENGTH,
    UnsafePayloadError,
    build_safe_payload,
)


def test_allowlisted_payload_passes_through() -> None:
    payload = {"from_status": "created", "to_status": "queued", "reason": "accepted"}
    assert build_safe_payload(EventType.RUN_STATUS_CHANGED, payload) == payload


def test_unknown_key_is_rejected_not_stored() -> None:
    with pytest.raises(UnsafePayloadError, match="not allowlisted"):
        build_safe_payload(EventType.RUN_CREATED, {"template_id": "x", "stdout": "secret"})


def test_nested_values_are_rejected() -> None:
    with pytest.raises(UnsafePayloadError):
        build_safe_payload(EventType.RUN_CREATED, {"template_id": {"nested": "x"}})


def test_float_values_are_rejected() -> None:
    with pytest.raises(UnsafePayloadError):
        build_safe_payload(EventType.RUN_CREATED, {"policy_version": 1.5})


def test_long_strings_are_rejected() -> None:
    with pytest.raises(UnsafePayloadError, match="longer than"):
        build_safe_payload(EventType.RUN_STATUS_CHANGED, {"reason": "x" * (MAX_STRING_LENGTH + 1)})


def test_every_event_type_has_an_allowlist() -> None:
    for event_type in EventType:
        build_safe_payload(event_type, {})
