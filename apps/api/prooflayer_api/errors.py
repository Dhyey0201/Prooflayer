"""Typed error envelope and exception handlers.

Every error response has the same shape. Internal exception details are
logged server-side only and never returned to the caller.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .enums import ErrorCode
from .request_id import current_request_id

logger = logging.getLogger("prooflayer.api")

_STATUS_TO_CODE = {
    400: ErrorCode.BAD_REQUEST,
    403: ErrorCode.READ_ONLY,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
}


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Raise from route code for an expected, typed failure."""

    def __init__(self, status_code: int, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _respond(status_code: int, code: ErrorCode, message: str) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=current_request_id())
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return _respond(exc.status_code, exc.code, exc.message)


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.BAD_REQUEST)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return _respond(exc.status_code, code, message)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Report field locations only; echoing input values could reflect secrets.
    fields = sorted({".".join(str(p) for p in err.get("loc", ())) for err in exc.errors()})
    return _respond(422, ErrorCode.VALIDATION_ERROR, "Invalid request: " + ", ".join(fields))


class UnhandledErrorMiddleware:
    """Convert uncaught exceptions into the typed 500 envelope.

    Runs inside ``RequestIdMiddleware`` so the response still carries the
    request ID. Only the exception type is logged, never its message.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            logger.error(
                "unhandled_error",
                extra={"request_id": current_request_id(), "error_type": type(exc).__name__},
            )
            if response_started:
                raise
            response = _respond(500, ErrorCode.INTERNAL_ERROR, "Internal server error")
            await response(scope, receive, send)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
