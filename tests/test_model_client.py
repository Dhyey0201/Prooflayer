from __future__ import annotations

from collections.abc import Sequence

import pytest

from prooflayer_api.ai.client import (
    CallOutcome,
    CallRecord,
    ChatMessage,
    ChatResult,
    CircuitBreaker,
    FatalModelError,
    ModelBudgetExceededError,
    ModelClient,
    ModelUnavailableError,
    RetryableModelError,
    RunBudget,
)

MESSAGES = [ChatMessage("system", "rules"), ChatMessage("user", "task with SECRET-PROMPT-TEXT")]


class FakeTransport:
    provider = "fake"
    model_id = "fake/model"

    def __init__(self, outcomes: Sequence[object], models: Sequence[str] = ("fake/model",)):
        self._outcomes = list(outcomes)
        self._models = list(models)
        self.calls = 0
        self.max_tokens_seen: list[int] = []

    def complete(self, messages, *, max_tokens: int) -> ChatResult:
        self.calls += 1
        self.max_tokens_seen.append(max_tokens)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def list_models(self) -> list[str]:
        if isinstance(self._models, Exception):
            raise self._models
        return self._models


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def ok(text: str = '{"action": "list_files"}', prompt: int = 10, completion: int = 5) -> ChatResult:
    return ChatResult(text, prompt, completion)


def make_client(transport, *, max_calls=12, max_tokens=20_000, breaker=None, retries=2):
    records: list[CallRecord] = []
    sleeps: list[float] = []
    client = ModelClient(
        transport=transport,
        budget=RunBudget(max_calls=max_calls, max_tokens=max_tokens),
        breaker=breaker or CircuitBreaker(),
        max_retries=retries,
        observer=records.append,
        sleep=sleeps.append,
        clock=Clock(),
    )
    return client, records, sleeps


def test_successful_call_counts_budget_and_records_metadata_only() -> None:
    client, records, _ = make_client(FakeTransport([ok(prompt=100, completion=20)]))
    result = client.complete(MESSAGES)
    assert result.content == '{"action": "list_files"}'
    assert client.budget.calls == 1
    assert client.budget.tokens == 120
    assert len(records) == 1
    record = records[0]
    assert record.outcome is CallOutcome.OK
    assert (record.prompt_tokens, record.completion_tokens) == (100, 20)
    # Records carry numbers and codes, never prompt or completion text.
    assert "SECRET-PROMPT-TEXT" not in repr(record)
    assert "list_files" not in repr(record)


def test_retryable_error_is_retried_with_backoff() -> None:
    transport = FakeTransport(
        [RetryableModelError("timeout"), RetryableModelError("http_503"), ok()]
    )
    client, records, sleeps = make_client(transport)
    client.complete(MESSAGES)
    assert transport.calls == 3
    assert sleeps == [0.5, 1.0]
    assert [r.outcome for r in records] == [
        CallOutcome.RETRYABLE_ERROR,
        CallOutcome.RETRYABLE_ERROR,
        CallOutcome.OK,
    ]
    assert [r.attempt for r in records] == [1, 2, 3]
    # One logical completion counts once against the call budget.
    assert client.budget.calls == 1


def test_retries_exhausted_raises_unavailable() -> None:
    transport = FakeTransport([RetryableModelError("timeout")] * 3)
    client, records, _ = make_client(transport)
    with pytest.raises(ModelUnavailableError, match="retries_exhausted:timeout"):
        client.complete(MESSAGES)
    assert transport.calls == 3
    assert all(r.error_code == "timeout" for r in records)


def test_fatal_error_is_not_retried() -> None:
    transport = FakeTransport([FatalModelError("http_401"), ok()])
    client, records, _ = make_client(transport)
    with pytest.raises(ModelUnavailableError, match="http_401"):
        client.complete(MESSAGES)
    assert transport.calls == 1
    assert records[0].outcome is CallOutcome.FATAL_ERROR


def test_call_budget_exhausted() -> None:
    client, _, _ = make_client(FakeTransport([ok(), ok()]), max_calls=1)
    client.complete(MESSAGES)
    with pytest.raises(ModelBudgetExceededError) as exc:
        client.complete(MESSAGES)
    assert exc.value.reason == "model_calls"


def test_token_budget_exhausted_and_caps_completion_tokens() -> None:
    transport = FakeTransport([ok(prompt=80, completion=20), ok()])
    client, _, _ = make_client(transport, max_tokens=100)
    client.complete(MESSAGES)
    assert transport.max_tokens_seen == [100]
    with pytest.raises(ModelBudgetExceededError) as exc:
        client.complete(MESSAGES)
    assert exc.value.reason == "model_tokens"
    assert transport.calls == 1


def test_circuit_breaker_opens_after_consecutive_failures_and_half_opens() -> None:
    clock = Clock()
    breaker = CircuitBreaker(threshold=3, cooldown_seconds=60, clock=clock)
    transport = FakeTransport([RetryableModelError("timeout")] * 3 + [ok()])
    client, records, _ = make_client(transport, breaker=breaker)
    with pytest.raises(ModelUnavailableError):
        client.complete(MESSAGES)
    assert breaker.is_open

    # While open, calls fail fast without touching the transport.
    with pytest.raises(ModelUnavailableError, match="circuit_open"):
        client.complete(MESSAGES)
    assert transport.calls == 3
    assert records[-1].outcome is CallOutcome.CIRCUIT_OPEN

    clock.now = 61
    assert client.complete(MESSAGES).content
    assert not breaker.is_open


def test_model_discovery() -> None:
    client, _, _ = make_client(FakeTransport([], models=["other", "fake/model"]))
    client.ensure_model_listed()

    missing, _, _ = make_client(FakeTransport([], models=["other"]))
    with pytest.raises(ModelUnavailableError, match="model_not_listed"):
        missing.ensure_model_listed()

    broken = FakeTransport([])
    broken._models = FatalModelError("http_401")
    failing, _, _ = make_client(broken)
    with pytest.raises(ModelUnavailableError, match="model_discovery_failed:http_401"):
        failing.ensure_model_listed()
