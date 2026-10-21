"""Nebius Token Factory transport (OpenAI-compatible chat completions).

Server-side only: the key comes from ``Settings`` and is passed straight to the
SDK, never logged or returned. SDK-level retries are disabled so ``ModelClient``
owns the retry, budget and circuit-breaker policy.
"""

from __future__ import annotations

from collections.abc import Sequence

import openai

from ..config import Settings
from .client import ChatMessage, ChatResult, FatalModelError, RetryableModelError

RETRYABLE_STATUS = frozenset({408, 409, 429})


def _estimate_tokens(text: str) -> int:
    # Used only when the provider omits usage, so the token budget still applies.
    return max(1, len(text) // 4)


class NebiusTransport:
    provider = "nebius"

    def __init__(self, settings: Settings, *, client: openai.OpenAI | None = None) -> None:
        if not settings.nebius_configured:
            raise FatalModelError("nebius_not_configured")
        self.model_id = settings.nebius_model_id
        self._client = client or openai.OpenAI(
            api_key=settings.nebius_api_key.get_secret_value(),
            base_url=settings.nebius_base_url,
            timeout=settings.model_timeout_seconds,
            max_retries=0,
        )

    def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> ChatResult:
        try:
            response = self._client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                max_tokens=max_tokens,
                temperature=0,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise _map_error(exc) from None
        content = (response.choices[0].message.content or "") if response.choices else ""
        usage = response.usage
        prompt_text = "".join(m.content for m in messages)
        return ChatResult(
            content=content,
            prompt_tokens=usage.prompt_tokens if usage else _estimate_tokens(prompt_text),
            completion_tokens=usage.completion_tokens if usage else _estimate_tokens(content),
        )

    def list_models(self) -> list[str]:
        try:
            return [model.id for model in self._client.models.list()]
        except Exception as exc:
            raise _map_error(exc) from None


def _map_error(exc: Exception) -> Exception:
    """Translate SDK errors into the two classes ``ModelClient`` understands.

    Only a short code is kept; SDK messages can echo request content.
    """
    if isinstance(exc, openai.APITimeoutError):
        return RetryableModelError("timeout")
    if isinstance(exc, openai.APIConnectionError):
        return RetryableModelError("connection_error")
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        if status in RETRYABLE_STATUS or status >= 500:
            return RetryableModelError(f"http_{status}")
        return FatalModelError(f"http_{status}")
    if isinstance(exc, openai.OpenAIError):
        return FatalModelError("sdk_error")
    return FatalModelError("unexpected_error")
