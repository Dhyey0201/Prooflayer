"""Per-run SHA-256 hash chain over canonical JSON.

This gives tamper *evidence*: modifying, deleting, inserting or reordering a
stored event breaks verification. It is not tamper *prevention*: anyone who
controls the whole store can rewrite every event and recompute the chain. A
detached manifest digest (Commit 11) is required to catch that.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

GENESIS_HASH = "0" * 64

# Fields covered by event_hash, in the wire names of contracts/openapi.yaml.
HASHED_FIELDS = (
    "run_id",
    "seq",
    "timestamp",
    "event_type",
    "actor",
    "safe_payload",
    "previous_hash",
)


def canonical_json(value: Any) -> bytes:
    """Deterministic UTF-8 JSON: sorted keys, no whitespace, no NaN/Infinity."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def format_timestamp(value: datetime) -> str:
    """UTC, microsecond precision, ``Z`` suffix. Naive values are read as UTC (SQLite)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_event_hash(event: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json({field: event[field] for field in HASHED_FIELDS}))


@dataclass(frozen=True)
class ChainVerification:
    valid: bool
    checked: int
    first_invalid_seq: int | None = None
    reason: str | None = None


def verify_chain(events: Iterable[Mapping[str, Any]]) -> ChainVerification:
    """Verify events in the order given (stored order, not re-sorted).

    Checks contiguous sequence numbers from 1, the previous-hash links and each
    recomputed hash. An empty chain is not valid evidence.
    """
    expected_previous = GENESIS_HASH
    checked = 0
    for index, event in enumerate(events, start=1):
        seq = event.get("seq")
        if seq != index:
            return ChainVerification(False, checked, seq, f"expected seq {index}, found {seq}")
        if event.get("previous_hash") != expected_previous:
            return ChainVerification(False, checked, seq, "previous_hash does not link")
        if compute_event_hash(event) != event.get("event_hash"):
            return ChainVerification(False, checked, seq, "event_hash mismatch")
        expected_previous = event["event_hash"]
        checked += 1
    if checked == 0:
        return ChainVerification(False, 0, None, "no events")
    return ChainVerification(True, checked)
