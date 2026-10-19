"""Redact-first event payloads.

Only allowlisted keys with bounded scalar values may be persisted. Anything
else is a programming error and is rejected rather than silently stored, so
free text (tool output, model responses, file contents) cannot leak into the
evidence log through an event payload.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..enums import EventType

MAX_STRING_LENGTH = 200

ALLOWED_PAYLOAD_KEYS: dict[EventType, frozenset[str]] = {
    EventType.RUN_CREATED: frozenset({"template_id", "mode", "policy_version"}),
    EventType.RUN_STATUS_CHANGED: frozenset({"from_status", "to_status", "reason"}),
}


class UnsafePayloadError(ValueError):
    pass


def build_safe_payload(event_type: EventType, payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed = ALLOWED_PAYLOAD_KEYS.get(event_type)
    if allowed is None:
        raise UnsafePayloadError(f"no payload allowlist for event type {event_type}")
    unknown = set(payload) - allowed
    if unknown:
        raise UnsafePayloadError(f"keys not allowlisted for {event_type}: {sorted(unknown)}")

    safe: dict[str, Any] = {}
    for key, value in payload.items():
        # bool is an int subclass; floats are excluded to keep hashing exact.
        if value is not None and not isinstance(value, str | int):
            raise UnsafePayloadError(f"{key}: only str, int, bool or None values are allowed")
        if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
            raise UnsafePayloadError(f"{key}: string longer than {MAX_STRING_LENGTH}")
        safe[key] = value
    return safe
