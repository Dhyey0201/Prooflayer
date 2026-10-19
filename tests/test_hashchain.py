from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from prooflayer_api.evidence.hashchain import (
    GENESIS_HASH,
    canonical_json,
    compute_event_hash,
    format_timestamp,
    verify_chain,
)

RUN_ID = "11111111-1111-4111-8111-111111111111"


def _chain(length: int = 3) -> list[dict]:
    events, previous = [], GENESIS_HASH
    for seq in range(1, length + 1):
        event = {
            "run_id": RUN_ID,
            "seq": seq,
            "timestamp": f"2026-10-19T10:00:0{seq}.000000Z",
            "event_type": "run.status_changed",
            "actor": "api",
            "safe_payload": {"from_status": "a", "to_status": "b", "reason": f"r{seq}"},
            "previous_hash": previous,
        }
        event["event_hash"] = compute_event_hash(event)
        previous = event["event_hash"]
        events.append(event)
    return events


def test_canonical_json_is_key_order_independent() -> None:
    assert canonical_json({"b": 1, "a": [2, "é"]}) == canonical_json({"a": [2, "é"], "b": 1})
    assert canonical_json({"a": 1}) == b'{"a":1}'


def test_canonical_json_rejects_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_timestamp_format_treats_naive_as_utc() -> None:
    aware = datetime(2026, 10, 19, 10, 0, 0, 123456, tzinfo=UTC)
    assert format_timestamp(aware) == "2026-10-19T10:00:00.123456Z"
    assert format_timestamp(aware.replace(tzinfo=None)) == "2026-10-19T10:00:00.123456Z"


def test_valid_chain_verifies() -> None:
    result = verify_chain(_chain())
    assert result.valid is True
    assert result.checked == 3


def test_empty_chain_is_not_valid_evidence() -> None:
    result = verify_chain([])
    assert result.valid is False
    assert result.reason == "no events"


def test_modified_payload_detected() -> None:
    events = _chain()
    events[1]["safe_payload"]["reason"] = "tampered"
    result = verify_chain(events)
    assert (result.valid, result.first_invalid_seq, result.reason) == (
        False,
        2,
        "event_hash mismatch",
    )


def test_modified_payload_with_recomputed_hash_breaks_next_link() -> None:
    events = _chain()
    events[1]["safe_payload"]["reason"] = "tampered"
    events[1]["event_hash"] = compute_event_hash(events[1])
    result = verify_chain(events)
    assert (result.valid, result.first_invalid_seq, result.reason) == (
        False,
        3,
        "previous_hash does not link",
    )


def test_deleted_event_detected() -> None:
    events = _chain()
    del events[1]
    result = verify_chain(events)
    assert result.valid is False
    assert result.first_invalid_seq == 3


def test_reordered_events_detected() -> None:
    events = _chain()
    events[1], events[2] = events[2], events[1]
    assert verify_chain(events).valid is False


def test_truncated_tail_is_undetectable_without_manifest() -> None:
    """Documented limit: dropping trailing events leaves a valid prefix."""
    assert verify_chain(_chain()[:2]).valid is True


def test_wrong_genesis_detected() -> None:
    events = _chain(1)
    events[0]["previous_hash"] = "f" * 64
    events[0]["event_hash"] = compute_event_hash(events[0])
    assert verify_chain(events).reason == "previous_hash does not link"


@pytest.mark.parametrize("field", ["run_id", "timestamp", "event_type", "actor"])
def test_every_hashed_field_is_covered(field: str) -> None:
    events = copy.deepcopy(_chain(1))
    events[0][field] = events[0][field] + "x"
    assert verify_chain(events).valid is False
