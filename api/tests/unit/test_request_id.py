"""Unit tests for request_id ContextVar + middleware.

The middleware's HTTP behavior is covered end-to-end by the existing
TestClient fixtures — here we just lock down the small surface:
default value outside a request, and header round-trip through the
middleware.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock


def test_default_request_id_is_dash():
    """Outside of any active request the ContextVar should read ``"-"``."""
    from request_id import get_request_id

    assert get_request_id() == "-"


def _run_middleware(incoming_headers: dict) -> tuple[dict, MagicMock]:
    """Drive the async middleware once; return (captured_state, response)."""
    from request_id import RequestIDMiddleware, get_request_id

    captured: dict[str, str] = {}

    async def call_next(req):
        captured["in_flight"] = get_request_id()
        resp = MagicMock()
        resp.headers = {}
        return resp

    req = MagicMock()
    req.headers = incoming_headers

    mw = RequestIDMiddleware(app=MagicMock())
    resp = asyncio.run(mw.dispatch(req, call_next))
    return captured, resp


def test_middleware_generates_id_when_missing():
    """If the inbound request has no X-Request-ID, the middleware mints a
    16-char hex id, stores it on the response header, and pops the
    ContextVar when done."""
    from request_id import HEADER_NAME, get_request_id

    captured, resp = _run_middleware({})

    assert captured["in_flight"] != "-"
    assert len(captured["in_flight"]) == 16  # hex slice length
    assert resp.headers[HEADER_NAME] == captured["in_flight"]
    # After dispatch, the ContextVar is reset.
    assert get_request_id() == "-"


def test_middleware_trusts_incoming_header():
    """An incoming X-Request-ID must be propagated verbatim (upstream
    gateways rely on the id staying identical across hops)."""
    from request_id import HEADER_NAME

    captured, resp = _run_middleware({HEADER_NAME: "upstream-abc-123"})

    assert captured["in_flight"] == "upstream-abc-123"
    assert resp.headers[HEADER_NAME] == "upstream-abc-123"
