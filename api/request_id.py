"""Per-request correlation ID — middleware + ContextVar.

When a request comes in we either trust the caller's ``X-Request-ID``
header (upstream gateways / retried curl commands can keep the same id
across hops) or mint a fresh 16-char hex id. The id lives in a
``ContextVar`` for the lifetime of the request, so any log line emitted
while handling it carries the same id — stitching chat turn → LLM call
→ DB writes → tool invocations in one grep.

The JSON formatter in ``main.py`` reads ``get_request_id()`` on every
log record. Outside a request (e.g. startup logs) the id is ``"-"``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

HEADER_NAME = "X-Request-ID"


def get_request_id() -> str:
    """Return the current request's id, or ``"-"`` if no request is active."""
    return _request_id.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Sets the request-id context for the duration of the request.

    Accepts an incoming ``X-Request-ID`` header verbatim if present, so
    a client/gateway can correlate logs across service hops. Otherwise
    generates a 16-char hex id — 2^64 space, plenty for uniqueness
    within a day of logs.
    """

    async def dispatch(self, request, call_next: Callable):
        rid = request.headers.get(HEADER_NAME) or uuid.uuid4().hex[:16]
        token = _request_id.set(rid)
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers[HEADER_NAME] = rid
        return response
