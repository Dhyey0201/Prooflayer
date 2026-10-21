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
    # ``enforced`` is True only when the runtime itself confirmed its policy is active.
    EventType.SANDBOX_PROVISIONED: frozenset(
        {"driver", "enforced", "policy_sha256", "image", "runtime_version"}
    ),
    EventType.SANDBOX_RELEASED: frozenset({"driver", "reason"}),
    # Metadata only: prompts and completions are never stored.
    EventType.MODEL_CALLED: frozenset(
        {
            "provider",
            "model_id",
            "attempt",
            "outcome",
            "prompt_tokens",
            "completion_tokens",
            "latency_ms",
            "error_code",
        }
    ),
    EventType.AGENT_ACTION_PROPOSED: frozenset({"step", "action", "target", "valid", "reason"}),
    # Tool output is hashed and measured, never stored.
    EventType.TOOL_RESULT: frozenset(
        {
            "step",
            "action",
            "target",
            "outcome",
            "exit_code",
            "output_bytes",
            "output_sha256",
            "truncated",
            "simulated",
        }
    ),
    # A denial is an *attempt* stopped at the enforcement point, never a disclosure.
    EventType.POLICY_DENIED: frozenset(
        {"step", "action", "target", "enforcement_point", "enforced", "source", "rule"}
    ),
    EventType.AGENT_CLAIMED: frozenset({"claim_sha256", "claim_chars", "tests_passed"}),
    EventType.AGENT_FINISHED: frozenset(
        {"outcome", "steps", "model_calls", "total_tokens", "model_id", "detail"}
    ),
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
