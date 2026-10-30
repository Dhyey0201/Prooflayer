"""Bounded model client.

Wraps a ``ModelTransport`` (Nebius Token Factory in live mode, a scripted
double in fixture mode and CI) with per-run budgets, bounded retries on
retryable errors and a process-wide circuit breaker. Every attempt is reported
to an observer as metadata only (tokens, latency, outcome); prompt and
completion text never leave this module except as the return value.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class ChatResult:
    content: str
    prompt_tokens: int
    completion_tokens: int


class RetryableModelError(Exception):
    """Timeout, connection reset, 408/409/429 or 5xx: worth another attempt."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FatalModelError(Exception):
    """Authentication, bad request, unknown model: retrying cannot help."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ModelTransport(Protocol):
    provider: str
    model_id: str

    def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> ChatResult: ...

    def list_models(self) -> list[str]: ...


class CallOutcome(StrEnum):
    OK = "ok"
    RETRYABLE_ERROR = "retryable_error"
    FATAL_ERROR = "fatal_error"
    CIRCUIT_OPEN = "circuit_open"


@dataclass(frozen=True)
class CallRecord:
    provider: str
    model_id: str
    attempt: int
    outcome: CallOutcome
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    error_code: str | None = None


class ModelUnavailableError(Exception):
    """No usable completion: retries exhausted, fatal error or circuit open."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ModelBudgetExceededError(Exception):
    def __init__(self, reason: Literal["model_calls", "model_tokens"]) -> None:
        super().__init__(reason)
        self.reason = reason


class CircuitBreaker:
    """Opens after ``threshold`` consecutive failed calls; half-opens after ``cooldown``."""

    def __init__(
        self,
        threshold: int = 3,
        cooldown_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = threshold
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            # Half-open: let one call through after the cooldown.
            return self._clock() - self._opened_at >= self._cooldown

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = self._clock()

    @property
    def is_open(self) -> bool:
        return not self.allow()


@dataclass
class RunBudget:
    """Hard per-run limits on model calls and total tokens."""

    max_calls: int
    max_tokens: int
    calls: int = 0
    tokens: int = 0

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.tokens)

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise ModelBudgetExceededError("model_calls")
        if self.remaining_tokens <= 0:
            raise ModelBudgetExceededError("model_tokens")


# Completion tokens requested per call; capped further by the remaining budget.
# Reasoning models (Nemotron 3 Super) count their thinking here too: at 1024 a live
# challenge reply was cut off mid-JSON (finish_reason=length), so leave headroom.
MAX_COMPLETION_TOKENS = 4096


@dataclass
class ModelClient:
    transport: ModelTransport
    budget: RunBudget
    breaker: CircuitBreaker
    max_retries: int = 2
    observer: Callable[[CallRecord], None] = lambda _record: None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    backoff_seconds: float = 0.5
    _attempt: int = field(default=0, init=False)

    @property
    def model_id(self) -> str:
        return self.transport.model_id

    def ensure_model_listed(self) -> None:
        """Model discovery: the configured ID must be served to this account."""
        try:
            models = self.transport.list_models()
        except (RetryableModelError, FatalModelError) as exc:
            raise ModelUnavailableError(f"model_discovery_failed:{exc.code}") from None
        if self.transport.model_id not in models:
            raise ModelUnavailableError("model_not_listed")

    def complete(self, messages: Sequence[ChatMessage]) -> ChatResult:
        """One logical completion, counted once against the call budget."""
        self.budget.check()
        self.budget.calls += 1
        max_tokens = min(MAX_COMPLETION_TOKENS, self.budget.remaining_tokens)
        last_code = "unknown"
        for retry in range(self.max_retries + 1):
            self._attempt += 1
            if not self.breaker.allow():
                self._record(CallOutcome.CIRCUIT_OPEN, 0, 0, 0, "circuit_open")
                raise ModelUnavailableError("circuit_open")
            started = self.clock()
            try:
                result = self.transport.complete(messages, max_tokens=max_tokens)
            except RetryableModelError as exc:
                last_code = exc.code
                self.breaker.record_failure()
                self._record(CallOutcome.RETRYABLE_ERROR, 0, 0, self._ms(started), exc.code)
                if retry < self.max_retries:
                    self.sleep(self.backoff_seconds * (2**retry))
                continue
            except FatalModelError as exc:
                self.breaker.record_failure()
                self._record(CallOutcome.FATAL_ERROR, 0, 0, self._ms(started), exc.code)
                raise ModelUnavailableError(exc.code) from None
            self.breaker.record_success()
            self.budget.tokens += result.prompt_tokens + result.completion_tokens
            self._record(
                CallOutcome.OK, result.prompt_tokens, result.completion_tokens, self._ms(started)
            )
            return result
        raise ModelUnavailableError(f"retries_exhausted:{last_code}")

    def _ms(self, started: float) -> int:
        return max(0, int((self.clock() - started) * 1000))

    def _record(
        self,
        outcome: CallOutcome,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        error_code: str | None = None,
    ) -> None:
        self.observer(
            CallRecord(
                provider=self.transport.provider,
                model_id=self.transport.model_id,
                attempt=self._attempt,
                outcome=outcome,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                error_code=error_code,
            )
        )
