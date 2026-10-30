"""HTTP hardening middleware: response security headers and a request body cap.

Every API body is a small JSON object (``RunCreate``) or empty, so bodies are
buffered up to ``MAX_REQUEST_BODY_BYTES`` and anything larger is refused with
the typed 413 envelope before a route sees it, whether or not the client sent
a ``Content-Length``.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .enums import ErrorCode
from .errors import _respond

MAX_REQUEST_BODY_BYTES = 64 * 1024

SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
)
# JSON responses only: the interactive /docs page loads its own scripts.
JSON_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers += [(k, v) for k, v in SECURITY_HEADERS if k not in present]
                content_type = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                if content_type.startswith(b"application/json"):
                    headers.append(JSON_CSP)
                    if b"cache-control" not in present:
                        # Evidence and run state must never be served from a shared cache.
                        headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def _too_large(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = _respond(413, ErrorCode.PAYLOAD_TOO_LARGE, "Request body too large")
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = self.max_bytes + 1
                if declared > self.max_bytes:
                    await self._too_large(scope, receive, send)
                    return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            size += len(body)
            if size > self.max_bytes:
                await self._too_large(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class ReadOnlyMiddleware:
    """Hosted replay mode: refuse every write before any route or worker sees it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in READ_METHODS:
            response = _respond(
                403, ErrorCode.READ_ONLY, "This deployment is a read-only replay of recorded runs"
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
