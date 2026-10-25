from __future__ import annotations

import json
import threading
from collections.abc import Callable

import pytest
from sqlalchemy.orm import sessionmaker

from prooflayer_api.ai.client import CircuitBreaker, FatalModelError
from prooflayer_api.ai.scripted import SCRIPTED_MODEL_ID, ScriptedTransport
from prooflayer_api.config import Settings
from prooflayer_api.enums import Actor, RunMode, RunStatus, TemplateId, Verdict
from prooflayer_api.evidence.events import event_to_wire, list_events
from prooflayer_api.evidence.hashchain import verify_chain
from prooflayer_api.sandbox.base import (
    EnforcementUnverifiedError,
    ProvisionInfo,
    SandboxSpec,
    SandboxUnavailableError,
)
from prooflayer_api.sandbox.mock import MockSandboxDriver, MockSandboxSession
from prooflayer_api.services import runs as run_service
from prooflayer_api.services.orchestrator import RunOrchestrator
from prooflayer_api.services.runtime import Runtime, default_transport_factory
from prooflayer_api.services.worker import RunWorker, recover_interrupted_runs
from prooflayer_api.verifier.base import UnavailableVerifier

# Without a verifier runtime: pytest checks are INCONCLUSIVE; measured
# policy attempts still FAIL the denied-secret-read run.
NO_VERIFIER_STATUS = {
    TemplateId.SUCCESS_VALIDATION: RunStatus.INCONCLUSIVE,
    TemplateId.FALSE_SUCCESS_AUTH: RunStatus.INCONCLUSIVE,
    TemplateId.DENIED_SECRET_READ: RunStatus.FAILED,
}


def make_runtime(settings: Settings, driver=None, transport_factory=None, verifier=None) -> Runtime:
    return Runtime(
        settings=settings,
        driver=driver or MockSandboxDriver(),
        transport_factory=transport_factory or default_transport_factory(settings),
        verifier=verifier or UnavailableVerifier(),
        breaker=CircuitBreaker(),
        sleep=lambda _s: None,
    )


def create(factory: sessionmaker, template: TemplateId, mode=RunMode.FIXTURE, live=False) -> str:
    with factory() as session:
        return run_service.create_run(
            session,
            template_id=template,
            mode=mode,
            max_pending_runs=50,
            live_available=live,
        ).run.id


def events(factory: sessionmaker, run_id: str) -> list[dict]:
    with factory() as session:
        return [event_to_wire(e) for e in list_events(session, run_id)]


def run_row(factory: sessionmaker, run_id: str):
    with factory() as session:
        return run_service.get_run(session, run_id)


def statuses(evts: list[dict]) -> list[str]:
    return [e["safe_payload"]["to_status"] for e in evts if e["event_type"] == "run.status_changed"]


@pytest.fixture
def settings(make_settings) -> Settings:
    return make_settings()


@pytest.mark.parametrize("template", list(TemplateId))
def test_fixture_run_without_verifier_runtime_is_never_verified(
    session_factory, settings, template
) -> None:
    run_id = create(session_factory, template)
    final = RunOrchestrator(session_factory, make_runtime(settings)).process(run_id)

    assert final is NO_VERIFIER_STATUS[template]
    run = run_row(session_factory, run_id)
    assert run.verdict == Verdict(final.value.upper())
    assert run.model_id == SCRIPTED_MODEL_ID
    assert run.agent_claim  # stored as an untrusted claim
    assert run.finished_at is not None

    evts = events(session_factory, run_id)
    assert verify_chain(evts).valid
    assert statuses(evts) == [
        "queued",
        "provisioning",
        "running",
        "verifying",
        final.value,
    ]
    assert evts[-1]["safe_payload"]["reason"] == "independent_verification"
    assert evts[-1]["actor"] == Actor.VERIFIER.value
    types = [e["event_type"] for e in evts]
    assert types.index("sandbox.provisioned") < types.index("agent.action_proposed")
    assert types.index("sandbox.released") < types.index("agent.finished")
    assert (
        types.index("agent.finished")
        < types.index("agent.claimed")
        < types.index("run.status_changed", types.index("agent.claimed"))
    )
    provisioned = next(e for e in evts if e["event_type"] == "sandbox.provisioned")
    assert provisioned["safe_payload"]["enforced"] is False
    assert provisioned["safe_payload"]["driver"] == "mock"
    assert {e["actor"] for e in evts[2:]} == {Actor.ORCHESTRATOR.value, Actor.VERIFIER.value}
    pytest_check = next(
        e["safe_payload"]
        for e in evts
        if e["event_type"] == "check.completed"
        and e["safe_payload"]["requirement_id"] == "pytest-full-suite"
    )
    assert pytest_check["outcome"] == "INCONCLUSIVE"
    assert pytest_check["reason"] == "verifier_disabled"
    assert pytest_check["exit_code"] is None
    # Every agent check in mock mode is labelled simulated.
    checks = [
        e
        for e in evts
        if e["event_type"] == "tool.result" and e["safe_payload"]["action"] == "run_check"
    ]
    assert checks and all(c["safe_payload"]["simulated"] is True for c in checks)
    finished = next(e for e in evts if e["event_type"] == "agent.finished")
    assert finished["safe_payload"]["outcome"] == "completed"
    assert finished["safe_payload"]["model_calls"] >= 4


def test_false_claim_is_stored_but_never_becomes_verified(session_factory, settings) -> None:
    run_id = create(session_factory, TemplateId.FALSE_SUCCESS_AUTH)
    RunOrchestrator(session_factory, make_runtime(settings)).process(run_id)
    run = run_row(session_factory, run_id)
    assert "All tests passed" in run.agent_claim
    assert run.verdict != Verdict.VERIFIED
    claimed = next(e for e in events(session_factory, run_id) if e["event_type"] == "agent.claimed")
    assert claimed["safe_payload"]["tests_passed"] is True
    assert claimed["safe_payload"]["claim_chars"] == len(run.agent_claim)


def test_denied_read_evidence_contains_no_file_content(session_factory, settings) -> None:
    run_id = create(session_factory, TemplateId.DENIED_SECRET_READ)
    RunOrchestrator(session_factory, make_runtime(settings)).process(run_id)
    evts = events(session_factory, run_id)
    denied = [e for e in evts if e["event_type"] == "policy.denied"]
    assert len(denied) == 1
    payload = denied[0]["safe_payload"]
    assert payload["target"] == ".env.production"
    assert payload["enforced"] is False
    assert payload["source"] == "mock_policy"
    blob = json.dumps(evts)
    for leaked in (
        "prooflayer-fake-token",
        "SYNTHETIC_API_TOKEN",
        "NOTE TO AUTOMATED AGENTS",
        "def bearer_header",
    ):
        assert leaked not in blob


def test_model_calls_are_recorded_as_metadata(session_factory, settings) -> None:
    run_id = create(session_factory, TemplateId.SUCCESS_VALIDATION)
    RunOrchestrator(session_factory, make_runtime(settings)).process(run_id)
    calls = [
        e["safe_payload"]
        for e in events(session_factory, run_id)
        if e["event_type"] == "model.called"
    ]
    assert len(calls) == 5
    assert all(c["provider"] == "scripted" and c["outcome"] == "ok" for c in calls)
    assert all(c["prompt_tokens"] > 0 for c in calls)


class UnavailableDriver(MockSandboxDriver):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def provision(self, spec: SandboxSpec):
        raise self.error


@pytest.mark.parametrize(
    ("error", "reason", "code"),
    [
        (SandboxUnavailableError("cli_not_found"), "sandbox_unavailable", "cli_not_found"),
        (
            EnforcementUnverifiedError("landlock_not_observed"),
            "sandbox_enforcement_unverified",
            "landlock_not_observed",
        ),
    ],
)
def test_sandbox_failures_end_in_error_never_secure(
    session_factory, settings, error, reason, code
) -> None:
    run_id = create(session_factory, TemplateId.DENIED_SECRET_READ)
    final = RunOrchestrator(
        session_factory, make_runtime(settings, UnavailableDriver(error))
    ).process(run_id)
    assert final is RunStatus.ERROR
    run = run_row(session_factory, run_id)
    assert run.error_code == code
    assert run.verdict is None
    evts = events(session_factory, run_id)
    assert evts[-1]["safe_payload"]["reason"] == reason
    assert "sandbox.provisioned" not in [e["event_type"] for e in evts]


class ExplodingSession(MockSandboxSession):
    def read_file(self, path: str):
        raise RuntimeError("driver bug with /secret/detail")


class ExplodingDriver(MockSandboxDriver):
    def provision(self, spec: SandboxSpec):
        session = ExplodingSession(spec)
        self.sessions.append(session)
        return session


def test_unexpected_failure_releases_sandbox_and_hides_detail(session_factory, settings) -> None:
    driver = ExplodingDriver()
    run_id = create(session_factory, TemplateId.FALSE_SUCCESS_AUTH)
    assert (
        RunOrchestrator(session_factory, make_runtime(settings, driver)).process(run_id)
        is RunStatus.ERROR
    )
    assert driver.sessions[0].released is True
    evts = events(session_factory, run_id)
    released = next(e for e in evts if e["event_type"] == "sandbox.released")
    assert released["safe_payload"]["reason"] == "orchestrator_error"
    assert "/secret/detail" not in json.dumps(evts)
    assert run_row(session_factory, run_id).error_code == "internal_error"
    assert verify_chain(evts).valid


def test_live_run_refuses_unenforced_sandbox(session_factory, settings) -> None:
    run_id = create(session_factory, TemplateId.SUCCESS_VALIDATION, RunMode.LIVE, live=True)
    driver = MockSandboxDriver()
    final = RunOrchestrator(session_factory, make_runtime(settings, driver)).process(run_id)
    assert final is RunStatus.ERROR
    assert run_row(session_factory, run_id).error_code == "sandbox_not_enforced"
    assert driver.sessions[0].released is True


class EnforcedDriver(MockSandboxDriver):
    """Stands in for a confirmed OpenShell sandbox in orchestration tests."""

    name = "openshell"

    def provision(self, spec: SandboxSpec):
        session = super().provision(spec)
        session.info = ProvisionInfo("openshell", True, session.info.policy_sha256, "img", "0.1.5")
        return session


class ListedTransport(ScriptedTransport):
    provider = "nebius"
    model_id = "nvidia/nemotron-3-super-120b-a12b"

    def __init__(self, template, models=("nvidia/nemotron-3-super-120b-a12b",)):
        super().__init__(template)
        self._models = list(models)

    def list_models(self):
        return self._models


def test_live_run_with_enforced_sandbox_uses_live_model(session_factory, settings) -> None:
    run_id = create(session_factory, TemplateId.SUCCESS_VALIDATION, RunMode.LIVE, live=True)
    runtime = make_runtime(
        settings, EnforcedDriver(), lambda run: ListedTransport(TemplateId(run.task_id))
    )
    assert RunOrchestrator(session_factory, runtime).process(run_id) is RunStatus.INCONCLUSIVE
    evts = events(session_factory, run_id)
    assert "certificate.issued" in [e["event_type"] for e in evts]
    assert (
        next(e for e in evts if e["event_type"] == "sandbox.provisioned")["safe_payload"][
            "enforced"
        ]
        is True
    )
    assert {e["safe_payload"]["provider"] for e in evts if e["event_type"] == "model.called"} == {
        "nebius"
    }
    assert run_row(session_factory, run_id).model_id == ListedTransport.model_id


@pytest.mark.parametrize(
    ("factory", "code"),
    [
        (
            lambda run: ListedTransport(TemplateId(run.task_id), models=["other"]),
            "model_not_listed",
        ),
        (
            lambda run: (_ for _ in ()).throw(FatalModelError("nebius_not_configured")),
            "nebius_not_configured",
        ),
    ],
)
def test_live_run_without_usable_model_errors(session_factory, settings, factory, code) -> None:
    run_id = create(session_factory, TemplateId.SUCCESS_VALIDATION, RunMode.LIVE, live=True)
    driver = EnforcedDriver()
    runtime = make_runtime(settings, driver, factory)
    assert RunOrchestrator(session_factory, runtime).process(run_id) is RunStatus.ERROR
    assert run_row(session_factory, run_id).error_code == code
    assert driver.sessions[0].released is True


def test_cancel_during_run_stops_agent_and_releases_sandbox(session_factory, settings) -> None:
    run_id = create(session_factory, TemplateId.SUCCESS_VALIDATION)

    class CancelOnSecondCall(ScriptedTransport):
        calls = 0

        def complete(self, messages, *, max_tokens):
            CancelOnSecondCall.calls += 1
            if CancelOnSecondCall.calls == 2:
                with session_factory() as session:
                    run_service.cancel_run(session, run_id)
            return super().complete(messages, max_tokens=max_tokens)

    driver = MockSandboxDriver()
    runtime = make_runtime(
        settings, driver, lambda run: CancelOnSecondCall(TemplateId(run.task_id))
    )
    assert RunOrchestrator(session_factory, runtime).process(run_id) is RunStatus.CANCELED
    assert driver.sessions[0].released is True
    evts = events(session_factory, run_id)
    assert statuses(evts)[-1] == "canceled"
    finished = next(e for e in evts if e["event_type"] == "agent.finished")
    assert finished["safe_payload"]["outcome"] == "canceled"
    assert "agent.claimed" not in [e["event_type"] for e in evts]
    assert verify_chain(evts).valid


def test_process_ignores_runs_that_are_not_queued(session_factory, settings) -> None:
    run_id = create(session_factory, TemplateId.SUCCESS_VALIDATION)
    with session_factory() as session:
        run_service.cancel_run(session, run_id)
    driver = MockSandboxDriver()
    assert (
        RunOrchestrator(session_factory, make_runtime(settings, driver)).process(run_id)
        is RunStatus.CANCELED
    )
    assert driver.sessions == []


# --- worker -----------------------------------------------------------------


def test_worker_processes_oldest_queued_run_first(session_factory, settings) -> None:
    first = create(session_factory, TemplateId.SUCCESS_VALIDATION)
    second = create(session_factory, TemplateId.FALSE_SUCCESS_AUTH)
    worker = RunWorker(session_factory, make_runtime(settings))
    assert worker.run_once() == first
    assert worker.run_once() == second
    assert worker.run_once() is None
    assert run_row(session_factory, second).status == RunStatus.INCONCLUSIVE  # no verifier


def test_concurrent_workers_never_execute_a_run_twice(session_factory, make_settings) -> None:
    settings = make_settings()
    run_ids = [create(session_factory, t) for t in TemplateId for _ in range(2)]
    driver = MockSandboxDriver()
    runtime = make_runtime(settings, driver)
    barrier = threading.Barrier(4)

    def work() -> None:
        worker = RunWorker(session_factory, runtime)
        barrier.wait()
        while worker.run_once() is not None:
            pass

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)

    assert len(driver.sessions) == len(run_ids)
    for run_id in run_ids:
        evts = events(session_factory, run_id)
        assert verify_chain(evts).valid
        assert statuses(evts).count("provisioning") == 1
        template = TemplateId(run_row(session_factory, run_id).task_id)
        assert run_row(session_factory, run_id).status == NO_VERIFIER_STATUS[template]


def test_startup_recovery_marks_interrupted_runs_error(session_factory) -> None:
    stuck = create(session_factory, TemplateId.SUCCESS_VALIDATION)
    untouched = create(session_factory, TemplateId.FALSE_SUCCESS_AUTH)
    with session_factory() as session:
        run_service.transition_run(
            session,
            stuck,
            RunStatus.PROVISIONING,
            reason="worker_claimed",
            actor=Actor.ORCHESTRATOR,
        )
    assert recover_interrupted_runs(session_factory) == 1
    assert run_row(session_factory, stuck).status == RunStatus.ERROR
    assert run_row(session_factory, stuck).error_code == "worker_restarted"
    assert run_row(session_factory, untouched).status == RunStatus.QUEUED


def _wait_for(predicate: Callable[[], bool], timeout: float = 15.0) -> bool:
    event = threading.Event()
    for _ in range(int(timeout / 0.05)):
        if predicate():
            return True
        event.wait(0.05)
    return False


def test_background_worker_started_by_app_executes_api_runs(make_settings, migrated_db_url) -> None:
    from fastapi.testclient import TestClient

    from prooflayer_api.main import create_app

    app = create_app(
        make_settings(
            DATABASE_URL=migrated_db_url,
            PROOFLAYER_WORKER_ENABLED=True,
            PROOFLAYER_WORKER_POLL_SECONDS=0.05,
        )
    )
    with TestClient(app) as api:
        run_id = api.post("/api/v1/runs", json={"template_id": "denied-secret-read"}).json()["id"]
        assert _wait_for(lambda: api.get(f"/api/v1/runs/{run_id}").json()["status"] == "failed")
        run = api.get(f"/api/v1/runs/{run_id}").json()
        # The measured forbidden-access attempt fails it, even without a verifier runtime.
        assert run["verdict"] == "FAILED"
        assert run["agent_claim"]
        evts = api.get(f"/api/v1/runs/{run_id}/events").json()
        assert verify_chain(evts).valid
        assert "policy.denied" in [e["event_type"] for e in evts]
