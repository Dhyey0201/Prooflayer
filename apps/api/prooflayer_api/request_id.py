"""Request ID middleware.

A caller-supplied ``X-Request-ID`` is accepted only if it matches a strict
pattern, so arbitrary header content never reaches logs or responses.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()


def _resolve(raw: str | None) -> str:
    if raw and _SAFE_REQUEST_ID.fullmatch(raw):
        return raw
    return str(uuid.uuid4())


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                raw = value.decode("latin-1")
                break
        request_id = _resolve(raw)
        token = request_id_var.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
