"""Service-level lifecycle tests, including concurrency on the SQLite store."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from prooflayer_api.db.models import Event, Run
from prooflayer_api.enums import Actor, EventType, RunMode, RunStatus, TemplateId, Verdict
from prooflayer_api.evidence.events import append_event, event_to_wire, list_events
from prooflayer_api.evidence.hashchain import verify_chain
from prooflayer_api.seed import main as seed_main
from prooflayer_api.services import runs as run_service
from prooflayer_api.services.state_machine import InvalidTransitionError

WORKERS = 8


def _new_run(factory: sessionmaker, key: str | None = None) -> str:
    with factory() as session:
        return run_service.create_run(
            session,
            template_id=TemplateId.FALSE_SUCCESS_AUTH,
            mode=RunMode.FIXTURE,
            max_pending_runs=100,
            idempotency_key=key,
        ).run.id


def _chain(factory: sessionmaker, run_id: str):
    with factory() as session:
        return verify_chain([event_to_wire(e) for e in list_events(session, run_id)])


def test_full_lifecycle_sets_verdict_and_timestamps(session_factory: sessionmaker) -> None:
    run_id = _new_run(session_factory)
    for target in (RunStatus.PROVISIONING, RunStatus.RUNNING, RunStatus.VERIFYING):
        with session_factory() as session:
            run_service.transition_run(
                session, run_id, target, reason="test", actor=Actor.ORCHESTRATOR
            )
    with session_factory() as session:
        run = run_service.transition_run(
            session, run_id, RunStatus.FAILED, reason="test", actor=Actor.ORCHESTRATOR
        )
        assert run.verdict == Verdict.FAILED
        assert run.started_at is not None
        assert run.finished_at is not None
    result = _chain(session_factory, run_id)
    assert result.valid is True
    assert result.checked == 6


def test_forbidden_transition_is_rejected_without_side_effects(
    session_factory: sessionmaker,
) -> None:
    run_id = _new_run(session_factory)
    with session_factory() as session, pytest.raises(InvalidTransitionError):
        run_service.transition_run(
            session, run_id, RunStatus.VERIFIED, reason="forged", actor=Actor.API
        )
    with session_factory() as session:
        run = run_service.get_run(session, run_id)
        assert run.status == RunStatus.QUEUED
        assert run.verdict is None
        assert len(list_events(session, run_id)) == 2


def test_cancel_terminal_run_is_rejected(session_factory: sessionmaker) -> None:
    run_id = _new_run(session_factory)
    with session_factory() as session:
        run_service.transition_run(session, run_id, RunStatus.ERROR, reason="t", actor=Actor.API)
    with session_factory() as session, pytest.raises(InvalidTransitionError):
        run_service.cancel_run(session, run_id)


def test_stale_version_is_a_concurrent_update(session_factory: sessionmaker) -> None:
    run_id = _new_run(session_factory)
    with session_factory() as session:
        run = run_service.get_run(session, run_id)
        # Simulate another writer bumping the row after we loaded it.
        session.execute(
            update(Run).where(Run.id == run_id).values(version=Run.version + 1),
            execution_options={"synchronize_session": False},
        )
        with pytest.raises(run_service.ConcurrentUpdateError):
            run_service.transition_run(
                session, run.id, RunStatus.CANCELED, reason="t", actor=Actor.API
            )


def test_concurrent_event_appends_get_contiguous_sequence(session_factory: sessionmaker) -> None:
    run_id = _new_run(session_factory)

    def append(i: int) -> int:
        with session_factory() as session:
            event = append_event(
                session,
                run_id,
                EventType.RUN_STATUS_CHANGED,
                Actor.ORCHESTRATOR,
                {"from_status": "queued", "to_status": "queued", "reason": f"probe-{i}"},
            )
            session.commit()
            return event.seq

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        seqs = sorted(pool.map(append, range(WORKERS * 3)))
    assert seqs == list(range(3, 3 + WORKERS * 3))
    result = _chain(session_factory, run_id)
    assert result.valid is True
    assert result.checked == 2 + WORKERS * 3


def test_concurrent_creates_with_same_idempotency_key_make_one_run(
    session_factory: sessionmaker,
) -> None:
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        ids = set(pool.map(lambda _: _new_run(session_factory, "same-key-123"), range(WORKERS)))
    assert len(ids) == 1
    with session_factory() as session:
        assert len(session.scalars(select(Run)).all()) == 1
        assert len(session.scalars(select(Event)).all()) == 2


def test_concurrent_cancels_record_one_transition(session_factory: sessionmaker) -> None:
    run_id = _new_run(session_factory)

    def cancel(_: int) -> RunStatus:
        with session_factory() as session:
            return run_service.cancel_run(session, run_id).status

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        statuses = set(pool.map(cancel, range(WORKERS)))
    assert statuses == {RunStatus.CANCELED}
    with session_factory() as session:
        types = [e.payload_json.get("to_status") for e in list_events(session, run_id)]
    assert types == [None, "queued", "canceled"]


def test_seed_command_is_idempotent_and_creates_real_runs(
    monkeypatch, migrated_db_url: str, capsys
) -> None:
    from prooflayer_api.config import get_settings

    monkeypatch.setenv("DATABASE_URL", migrated_db_url)
    get_settings.cache_clear()
    try:
        seed_main([])
        seed_main(["--with-runs"])
    finally:
        get_settings.cache_clear()
    output = capsys.readouterr().out
    assert output.count("Seeded 3 fixture templates") == 2
    assert output.count("Created run") == 3

    from prooflayer_api.db.session import make_engine, make_session_factory

    engine = make_engine(migrated_db_url)
    factory = make_session_factory(engine)
    with factory() as session:
        runs = session.scalars(select(Run)).all()
        assert {r.status for r in runs} == {RunStatus.QUEUED}
        for run in runs:
            events = [event_to_wire(e) for e in list_events(session, run.id)]
            assert verify_chain(events).valid is True
            assert {e["actor"] for e in events} == {"seeder"}
    engine.dispose()
