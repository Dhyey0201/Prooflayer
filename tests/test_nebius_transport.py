"""NebiusTransport through the real OpenAI SDK against an in-process HTTP double.

No request leaves the process: ``httpx2.MockTransport`` answers every call.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import openai
import pytest

from prooflayer_api.ai.client import ChatMessage, FatalModelError, RetryableModelError
from prooflayer_api.ai.nebius import NebiusTransport
from tests.conftest import FAKE_NEBIUS_KEY

MODEL = "nvidia/nemotron-3-super-120b-a12b"


def _completion(content: str | None, usage: bool = True) -> dict:
    body = {
        "id": "c1",
        "object": "chat.completion",
        "created": 0,
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    if usage:
        body["usage"] = {"prompt_tokens": 42, "completion_tokens": 7, "total_tokens": 49}
    return body


def make_transport(make_settings, handler: Callable[[httpx2.Request], httpx2.Response]):
    settings = make_settings(NEBIUS_API_KEY=FAKE_NEBIUS_KEY, PROOFLAYER_MOCK_MODE=False)
    client = openai.OpenAI(
        api_key=settings.nebius_api_key.get_secret_value(),
        base_url=settings.nebius_base_url,
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return NebiusTransport(settings, client=client)


def test_completion_request_shape_and_usage(make_settings) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=_completion('{"action": "list_files"}'))

    transport = make_transport(make_settings, handler)
    result = transport.complete([ChatMessage("user", "hi")], max_tokens=256)

    assert result.content == '{"action": "list_files"}'
    assert (result.prompt_tokens, result.completion_tokens) == (42, 7)
    request = seen[0]
    assert request.url.host == "api.tokenfactory.us-central1.nebius.com"
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_NEBIUS_KEY}"
    body = json.loads(request.content)
    assert body["model"] == MODEL
    assert body["max_tokens"] == 256
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}


def test_missing_usage_is_estimated_so_budget_still_applies(make_settings) -> None:
    transport = make_transport(
        make_settings, lambda r: httpx2.Response(200, json=_completion("x" * 40, usage=False))
    )
    result = transport.complete([ChatMessage("user", "y" * 80)], max_tokens=10)
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 10


def test_list_models(make_settings) -> None:
    payload = {
        "object": "list",
        "data": [{"id": MODEL, "object": "model", "created": 0, "owned_by": "nvidia"}],
    }
    transport = make_transport(make_settings, lambda r: httpx2.Response(200, json=payload))
    assert transport.list_models() == [MODEL]


@pytest.mark.parametrize(
    ("status", "error_type", "code"),
    [
        (429, RetryableModelError, "http_429"),
        (500, RetryableModelError, "http_500"),
        (503, RetryableModelError, "http_503"),
        (408, RetryableModelError, "http_408"),
        (401, FatalModelError, "http_401"),
        (400, FatalModelError, "http_400"),
        (404, FatalModelError, "http_404"),
    ],
)
def test_http_errors_are_classified(make_settings, status, error_type, code) -> None:
    transport = make_transport(
        make_settings,
        lambda r: httpx2.Response(status, json={"error": {"message": f"echo {FAKE_NEBIUS_KEY}"}}),
    )
    with pytest.raises(error_type) as exc:
        transport.complete([ChatMessage("user", "hi")], max_tokens=10)
    assert exc.value.code == code
    # Only the short code survives; provider messages are dropped.
    assert FAKE_NEBIUS_KEY not in str(exc.value)


def test_timeout_and_connection_errors_are_retryable(make_settings) -> None:
    def timeout(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    def refused(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(RetryableModelError, match="timeout"):
        make_transport(make_settings, timeout).complete([ChatMessage("user", "x")], max_tokens=1)
    with pytest.raises(RetryableModelError, match="connection_error"):
        make_transport(make_settings, refused).complete([ChatMessage("user", "x")], max_tokens=1)


def test_requires_configured_key(make_settings) -> None:
    with pytest.raises(FatalModelError, match="nebius_not_configured"):
        NebiusTransport(make_settings())
