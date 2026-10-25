"""Executes one run: provision sandbox -> bounded agent -> snapshot -> release -> verify.

The orchestrator writes the agent-side evidence and the independent verifier
(``services.verification``) writes check results and the certificate; the agent
writes nothing. Each event is committed in its own transaction as it happens,
so a crash still leaves an ordered, valid chain. The agent's own claim and
checks are never promoted to a verdict: the verdict comes from the verifier's
measurements only, and is INCONCLUSIVE whenever they are missing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from ..agent.planner import AgentOutcome, AgentResult, BoundedAgent
from ..ai.client import CallRecord, FatalModelError, ModelUnavailableError
from ..enums import Actor, EventType, RunMode, RunStatus, TemplateId
from ..evidence.events import append_event
from ..sandbox.base import (
    Denial,
    EnforcementUnverifiedError,
    ProvisionInfo,
    SandboxSession,
    SandboxSpec,
    SandboxUnavailableError,
    ToolResult,
)
from . import runs as run_service
from .fixtures import get_fixture
from .runtime import Runtime
from .state_machine import InvalidTransitionError
from .verification import AgentRunState, RunVerifier
from .workspace_paths import snapshot_paths

log = logging.getLogger(__name__)


class _Evidence:
    """Appends orchestrator events for one run, one transaction per event."""

    def __init__(self, session_factory: sessionmaker, run_id: str) -> None:
        self._factory = session_factory
        self.run_id = run_id

    def event(self, event_type: EventType, payload: dict[str, Any]) -> None:
        with self._factory.begin() as session:
            append_event(session, self.run_id, event_type, Actor.ORCHESTRATOR, payload)

    # AgentRecorder protocol --------------------------------------------------

    def action_proposed(
        self, step: int, action: str, target: str, *, valid: bool, reason: str
    ) -> None:
        self.event(
            EventType.AGENT_ACTION_PROPOSED,
            {"step": step, "action": action, "target": target, "valid": valid, "reason": reason},
        )

    def tool_result(self, step: int, action: str, target: str, result: ToolResult) -> None:
        self.event(
            EventType.TOOL_RESULT,
            {
                "step": step,
                "action": action,
                "target": target,
                "outcome": result.outcome.value,
                "exit_code": result.exit_code,
                "output_bytes": result.output_bytes,
                "output_sha256": result.output_sha256,
                "truncated": result.truncated,
                "simulated": result.simulated,
            },
        )

    def denial(self, step: int, denial: Denial) -> None:
        self.event(
            EventType.POLICY_DENIED,
            {
                "step": step,
                "action": denial.action,
                "target": denial.target,
                "enforcement_point": denial.enforcement_point,
                "enforced": denial.enforced,
                "source": denial.source,
                "rule": denial.rule,
            },
        )

    def model_call(self, record: CallRecord) -> None:
        self.event(
            EventType.MODEL_CALLED,
            {
                "provider": record.provider,
                "model_id": record.model_id,
                "attempt": record.attempt,
                "outcome": record.outcome.value,
                "prompt_tokens": record.prompt_tokens,
                "completion_tokens": record.completion_tokens,
                "latency_ms": record.latency_ms,
                "error_code": record.error_code,
            },
        )


class RunOrchestrator:
    def __init__(self, session_factory: sessionmaker, runtime: Runtime) -> None:
        self._factory = session_factory
        self._runtime = runtime

    # -- run state helpers ---------------------------------------------------

    def _read(self, run_id: str, fn: Callable[[Any], Any]) -> Any:
        with self._factory() as session:
            return fn(run_service.get_run(session, run_id))

    def _status(self, run_id: str) -> RunStatus:
        return RunStatus(self._read(run_id, lambda run: run.status))

    def _transition(self, run_id: str, target: RunStatus, reason: str, **fields: Any) -> bool:
        """Apply a transition; False if the run moved elsewhere (e.g. canceled)."""
        for _attempt in range(2):
            session: Session = self._factory()
            try:
                run_service.transition_run(
                    session, run_id, target, reason=reason, actor=Actor.ORCHESTRATOR, **fields
                )
                return True
            except InvalidTransitionError:
                return False
            except run_service.ConcurrentUpdateError:
                continue
            finally:
                session.close()
        return False

    def _fail(self, run_id: str, reason: str, error_code: str) -> None:
        self._transition(run_id, RunStatus.ERROR, reason, error_code=error_code[:64])

    # -- main entry point ----------------------------------------------------

    def process(self, run_id: str) -> RunStatus:
        """Execute a queued run to a terminal (or canceled) state."""
        if not self._transition(run_id, RunStatus.PROVISIONING, "worker_claimed"):
            return self._status(run_id)
        try:
            self._execute(run_id)
        except Exception:
            # Never leak exception text into evidence; the log keeps the traceback.
            log.exception("run %s failed in orchestrator", run_id)
            self._fail(run_id, "internal_error", "internal_error")
        return self._status(run_id)

    def _execute(self, run_id: str) -> None:
        settings = self._runtime.settings
        template_id, mode = self._read(run_id, lambda r: (TemplateId(r.task_id), RunMode(r.mode)))
        fixture = get_fixture(template_id)
        evidence = _Evidence(self._factory, run_id)
        spec = SandboxSpec(
            run_id=run_id,
            fixture=fixture,
            timeout_seconds=settings.max_run_seconds,
            max_output_bytes=settings.max_output_bytes,
        )

        try:
            sandbox = self._runtime.driver.provision(spec)
        except SandboxUnavailableError as exc:
            self._fail(run_id, "sandbox_unavailable", exc.reason)
            return
        except EnforcementUnverifiedError as exc:
            self._fail(run_id, "sandbox_enforcement_unverified", exc.reason)
            return

        release_reason = "run_finished"
        try:
            info = sandbox.info
            evidence.event(
                EventType.SANDBOX_PROVISIONED,
                {
                    "driver": info.driver,
                    "enforced": info.enforced,
                    "policy_sha256": info.policy_sha256,
                    "image": info.image[:200],
                    "runtime_version": info.runtime_version[:200],
                },
            )
            if mode is RunMode.LIVE and not info.enforced:
                release_reason = "sandbox_not_enforced"
                self._fail(run_id, "sandbox_not_enforced", "sandbox_not_enforced")
                return
            result, client = self._run_agent(run_id, mode, sandbox, evidence)
            if result is None:
                release_reason = "model_unavailable"
                return
            observed = self._snapshot(run_id, sandbox, fixture)
        except BaseException:
            release_reason = "orchestrator_error"
            raise
        finally:
            sandbox.release()
            evidence.event(
                EventType.SANDBOX_RELEASED,
                {"driver": sandbox.info.driver, "reason": release_reason},
            )

        evidence.event(
            EventType.AGENT_FINISHED,
            {
                "outcome": result.outcome.value,
                "steps": result.steps,
                "model_calls": client.budget.calls,
                "total_tokens": client.budget.tokens,
                "model_id": client.model_id[:200],
                "detail": (result.detail or "-")[:200],
            },
        )
        self._conclude(run_id, result, client, sandbox.info, observed)

    def _snapshot(self, run_id: str, sandbox: SandboxSession, fixture) -> dict | None:
        """The agent's final workspace, read before the sandbox is released."""
        if self._status(run_id) is RunStatus.CANCELED:
            return None
        try:
            return sandbox.snapshot(snapshot_paths(fixture))
        except Exception:
            # Missing evidence makes the affected checks INCONCLUSIVE; never fatal.
            log.exception("workspace snapshot failed for run %s", run_id)
            return None

    def _run_agent(
        self, run_id: str, mode: RunMode, sandbox: SandboxSession, evidence: _Evidence
    ) -> tuple[AgentResult | None, Any]:
        runtime = self._runtime
        run = self._read(run_id, lambda r: r)
        try:
            client = runtime.model_client(run, evidence.model_call)
            if mode is RunMode.LIVE:
                client.ensure_model_listed()
        except (FatalModelError, ModelUnavailableError) as exc:
            code = getattr(exc, "code", None) or getattr(exc, "reason", "model_unavailable")
            self._fail(run_id, "model_unavailable", code)
            return None, None

        if not self._transition(
            run_id, RunStatus.RUNNING, "agent_started", model_id=client.model_id[:200]
        ):
            return AgentResult(AgentOutcome.CANCELED, 0), client
        agent = BoundedAgent(
            client=client,
            session=sandbox,
            fixture=get_fixture(TemplateId(run.task_id)),
            recorder=evidence,
            max_steps=runtime.settings.max_agent_steps,
            deadline=runtime.clock() + runtime.settings.max_run_seconds,
            should_stop=lambda: self._status(run_id) is RunStatus.CANCELED,
            clock=runtime.clock,
        )
        return agent.run(), client

    def _conclude(
        self,
        run_id: str,
        result: AgentResult,
        client: Any,
        info: ProvisionInfo,
        observed: dict | None,
    ) -> None:
        if result.outcome is AgentOutcome.CANCELED or self._status(run_id) is not RunStatus.RUNNING:
            return
        if result.claim is not None:
            with self._factory() as session:
                run_service.record_agent_claim(
                    session,
                    run_id,
                    summary=result.claim.summary,
                    tests_passed=result.claim.tests_passed,
                )
        if not self._transition(run_id, RunStatus.VERIFYING, f"agent_{result.outcome.value}"):
            return
        fixture = get_fixture(self._read(run_id, lambda r: TemplateId(r.task_id)))
        RunVerifier(self._factory, self._runtime).verify(
            run_id,
            fixture,
            AgentRunState(
                agent_outcome=result.outcome.value,
                claim_text=result.claim.summary if result.claim else None,
                claim_tests_passed=result.claim.tests_passed if result.claim else None,
                model_id=client.model_id,
                sandbox_driver=info.driver,
                sandbox_enforced=info.enforced,
                policy_sha256=info.policy_sha256,
                observed=observed,
            ),
        )
