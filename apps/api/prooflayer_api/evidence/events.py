"""Append-only event log with a per-run hash chain."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Event
from ..enums import Actor, EventType
from .hashchain import GENESIS_HASH, compute_event_hash, format_timestamp
from .safe_payload import build_safe_payload


def event_to_wire(event: Event) -> dict[str, Any]:
    """Contract shape of an event (contracts/openapi.yaml ``Event``)."""
    return {
        "run_id": event.run_id,
        "seq": event.seq,
        "timestamp": format_timestamp(event.time),
        "event_type": event.type,
        "actor": event.actor,
        "safe_payload": event.payload_json,
        "previous_hash": event.prev_hash,
        "event_hash": event.event_hash,
    }


def append_event(
    session: Session,
    run_id: str,
    event_type: EventType,
    actor: Actor,
    payload: Mapping[str, Any],
) -> Event:
    """Append the next event for ``run_id`` inside the caller's transaction.

    The caller must hold the database write lock (SQLite ``BEGIN IMMEDIATE``)
    so sequence allocation cannot race; the ``(run_id, seq)`` unique
    constraint is the backstop if it does.
    """
    last = session.execute(
        select(Event.seq, Event.event_hash)
        .where(Event.run_id == run_id)
        .order_by(Event.seq.desc())
        .limit(1)
    ).first()
    seq = 1 if last is None else last.seq + 1
    previous_hash = GENESIS_HASH if last is None else last.event_hash

    event = Event(
        run_id=run_id,
        seq=seq,
        time=datetime.now(UTC),
        type=event_type.value,
        actor=actor.value,
        payload_json=build_safe_payload(event_type, payload),
        prev_hash=previous_hash,
    )
    event.event_hash = compute_event_hash(event_to_wire(event))
    session.add(event)
    session.flush()
    return event


def list_events(
    session: Session, run_id: str, after_seq: int = 0, limit: int = 1000
) -> list[Event]:
    return list(
        session.scalars(
            select(Event)
            .where(Event.run_id == run_id, Event.seq > after_seq)
            .order_by(Event.seq)
            .limit(limit)
        )
    )
