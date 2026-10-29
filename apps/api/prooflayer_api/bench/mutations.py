"""Post-issue tampering of a certificate and its event log.

Each mutation works on copies of the served wire shapes (certificate JSON and
event list) and models an attacker with write access to the database. The
benchmark counts how many ``verify_certificate`` detects. ``full_rewrite``
recomputes every hash and digest, so only a detached copy of the manifest
digest (the ledger) can expose it; that is measured and reported separately.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from ..evidence.hashchain import GENESIS_HASH, compute_event_hash
from ..verifier.certificate import certificate_digest, content_digest, manifest_digest

Mutation = Callable[[dict[str, Any], list[dict[str, Any]]], None]
_OTHER_VERDICT = {"VERIFIED": "FAILED", "FAILED": "VERIFIED", "INCONCLUSIVE": "VERIFIED"}


def _middle(events: list[dict[str, Any]]) -> int:
    return max(1, len(events) // 2)


def edit_event_payload(cert: dict[str, Any], events: list[dict[str, Any]]) -> None:
    events[_middle(events)]["safe_payload"]["reason"] = "rewritten"


def delete_event(cert: dict[str, Any], events: list[dict[str, Any]]) -> None:
    del events[_middle(events)]


def reorder_events(cert: dict[str, Any], events: list[dict[str, Any]]) -> None:
    i = _middle(events)
    events[i - 1], events[i] = events[i], events[i - 1]


def edit_certificate_verdict(cert: dict[str, Any], events: list[dict[str, Any]]) -> None:
    verdict = _OTHER_VERDICT[cert["verdict"]]
    cert["verdict"] = cert["manifest"]["verdict"] = verdict


def full_rewrite(cert: dict[str, Any], events: list[dict[str, Any]]) -> None:
    """Change the verdict and recompute the chain, manifest and issued event."""
    verdict = _OTHER_VERDICT[cert["verdict"]]
    cert["verdict"] = cert["manifest"]["verdict"] = verdict
    cert["manifest"]["content_sha256"] = content_digest(cert)
    through = cert["manifest"]["events_through_seq"]
    previous = GENESIS_HASH
    for event in events:
        event["previous_hash"] = previous
        if event["event_type"] == "certificate.issued" and event["seq"] == through + 1:
            cert["manifest"]["event_chain_head"] = events[through - 1]["event_hash"]
            cert["evidence_manifest_sha256"] = manifest_digest(cert["manifest"])
            event["safe_payload"] = {
                **event["safe_payload"],
                "verdict": verdict,
                "manifest_sha256": cert["evidence_manifest_sha256"],
                "certificate_sha256": certificate_digest(cert),
            }
        event["event_hash"] = previous = compute_event_hash(event)


MUTATIONS: dict[str, Mutation] = {
    "edit_event_payload": edit_event_payload,
    "delete_event": delete_event,
    "reorder_events": reorder_events,
    "edit_certificate_verdict": edit_certificate_verdict,
    "full_rewrite": full_rewrite,
}


def mutated(
    name: str, cert: dict[str, Any], events: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cert, events = copy.deepcopy(cert), copy.deepcopy(events)
    MUTATIONS[name](cert, events)
    return cert, events
