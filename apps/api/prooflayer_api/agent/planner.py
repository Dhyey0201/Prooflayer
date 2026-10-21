"""Bounded step loop: model proposes one allowlisted action, the sandbox executes it.

Hard limits: ``max_steps`` executed actions, the model client's call and token
budget, and a wall-clock deadline. One malformed reply gets one corrective
retry; a second in a row ends the run as ``model_output_invalid``. The loop
never decides whether the task succeeded: ``finish`` yields an untrusted claim.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ..ai.client import ChatMessage, ModelBudgetExceededError, ModelClient, ModelUnavailableError
from ..sandbox.base import Denial, SandboxSession, ToolResult
from ..services.fixtures import FixtureTemplate
from . import prompts
from .actions import (
    Finish,
    InvalidActionError,
    ListFiles,
    ReadFile,
    RunCheck,
    WriteFile,
    parse_action,
)

# Model text echoed back as conversation history is capped.
MAX_ECHO_CHARS = 2_000
MAX_CHECK_SECONDS = 60.0


class AgentOutcome(StrEnum):
    COMPLETED = "completed"
    STEP_LIMIT = "step_limit"
    MODEL_BUDGET_EXHAUSTED = "model_budget_exhausted"
    MODEL_OUTPUT_INVALID = "model_output_invalid"
    MODEL_UNAVAILABLE = "model_unavailable"
    CANCELED = "canceled"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class AgentResult:
    outcome: AgentOutcome
    steps: int
    claim: Finish | None = None
    detail: str | None = None


class AgentRecorder(Protocol):
    def action_proposed(
        self, step: int, action: str, target: str, *, valid: bool, reason: str
    ) -> None: ...

    def tool_result(self, step: int, action: str, target: str, result: ToolResult) -> None: ...

    def denial(self, step: int, denial: Denial) -> None: ...


class BoundedAgent:
    def __init__(
        self,
        *,
        client: ModelClient,
        session: SandboxSession,
        fixture: FixtureTemplate,
        recorder: AgentRecorder,
        max_steps: int,
        deadline: float,
        should_stop: Callable[[], bool] = lambda: False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._session = session
        self._fixture = fixture
        self._recorder = recorder
        self._max_steps = max_steps
        self._deadline = deadline
        self._should_stop = should_stop
        self._clock = clock

    def run(self) -> AgentResult:
        messages = [
            ChatMessage("system", prompts.SYSTEM_PROMPT),
            ChatMessage("user", prompts.task_prompt(self._fixture, self._max_steps)),
        ]
        step = 0
        retried = False
        while step < self._max_steps:
            if self._should_stop():
                return AgentResult(AgentOutcome.CANCELED, step)
            if self._clock() >= self._deadline:
                return AgentResult(AgentOutcome.TIMEOUT, step)
            try:
                completion = self._client.complete(messages)
            except ModelBudgetExceededError as exc:
                return AgentResult(AgentOutcome.MODEL_BUDGET_EXHAUSTED, step, detail=exc.reason)
            except ModelUnavailableError as exc:
                return AgentResult(AgentOutcome.MODEL_UNAVAILABLE, step, detail=exc.reason)

            echo = ChatMessage("assistant", completion.content[:MAX_ECHO_CHARS])
            try:
                action = parse_action(completion.content)
            except InvalidActionError as exc:
                self._recorder.action_proposed(
                    step + 1, "invalid", "-", valid=False, reason=exc.code
                )
                if retried:
                    return AgentResult(AgentOutcome.MODEL_OUTPUT_INVALID, step, detail=exc.code)
                retried = True
                messages += [echo, ChatMessage("user", prompts.correction(exc.code, exc.detail))]
                continue

            retried = False
            step += 1
            self._recorder.action_proposed(
                step, action.action, action.target, valid=True, reason="-"
            )
            if isinstance(action, Finish):
                return AgentResult(AgentOutcome.COMPLETED, step, claim=action)

            result = self._execute(action)
            self._recorder.tool_result(step, action.action, action.target, result)
            if result.denial is not None:
                self._recorder.denial(step, result.denial)
            for denial in self._session.drain_denials():
                self._recorder.denial(step, denial)
            observation = prompts.observation(step, action.action, action.target, result)
            messages += [echo, ChatMessage("user", observation)]
        return AgentResult(AgentOutcome.STEP_LIMIT, step)

    def _execute(self, action: ListFiles | ReadFile | WriteFile | RunCheck) -> ToolResult:
        match action:
            case ListFiles():
                return self._session.list_files()
            case ReadFile(path=path):
                return self._session.read_file(path)
            case WriteFile(path=path, content=content):
                return self._session.write_file(path, content)
            case RunCheck(check_id=check_id):
                remaining = max(1.0, self._deadline - self._clock())
                return self._session.run_check(check_id, min(MAX_CHECK_SECONDS, remaining))
