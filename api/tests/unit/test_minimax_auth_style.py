"""Tests for MiniMax auth-header style switching.

The standard MiniMax pay-as-you-go API uses Anthropic's `x-api-key` header.
The Token/Coding Plan API requires `Authorization: Bearer <key>` instead.
This module verifies:

  1. ModelSpec.auth_style toggles which header _call_one_sync sends
  2. Coding-Plan keys (sk-cp- prefix) auto-detect to bearer at config load
  3. Explicit MINIMAX_AUTH_STYLE=bearer overrides the default
  4. Unknown values fall back to x-api-key (don't fail the import)
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


def test_model_spec_default_auth_style_is_x_api_key():
    from models import ModelSpec

    spec = ModelSpec(
        id="t",
        display_name="t",
        provider="minimax",
        api_url="https://example.com",
        api_key="k",
        api_model="m",
        anthropic_version="2023-06-01",
        input_weight=1.0,
        output_weight=4.0,
    )
    assert spec.auth_style == "x-api-key"


def test_model_spec_can_set_bearer():
    from models import ModelSpec

    spec = ModelSpec(
        id="t",
        display_name="t",
        provider="minimax",
        api_url="https://example.com",
        api_key="sk-cp-xyz",
        api_model="MiniMax-M2.7",
        anthropic_version="2023-06-01",
        input_weight=1.0,
        output_weight=4.0,
        auth_style="bearer",
    )
    assert spec.auth_style == "bearer"


def _fake_response(json_payload):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = json_payload
    r.text = ""
    return r


def _spec(auth_style: str):
    from models import ModelSpec

    return ModelSpec(
        id="t",
        display_name="t",
        provider="minimax",
        api_url="https://example.com/v1/messages",
        api_key="sk-cp-test123",
        api_model="MiniMax-M2.7",
        anthropic_version="2023-06-01",
        input_weight=1.0,
        output_weight=4.0,
        auth_style=auth_style,
    )


def test_x_api_key_style_sends_x_api_key_header():
    from services.external import llm

    captured: dict = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return _fake_response({"content": [{"type": "text", "text": "ok"}], "usage": {}})

    with patch.object(llm._http_client, "post", side_effect=fake_post):
        out = llm._call_one_sync(
            _spec("x-api-key"), "sys", [{"role": "user", "content": "hi"}], 100, 30.0
        )

    assert out == "ok"
    assert captured["headers"]["x-api-key"] == "sk-cp-test123"
    assert "Authorization" not in captured["headers"]


def test_bearer_style_sends_authorization_header():
    from services.external import llm

    captured: dict = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return _fake_response({"content": [{"type": "text", "text": "ok"}], "usage": {}})

    with patch.object(llm._http_client, "post", side_effect=fake_post):
        out = llm._call_one_sync(
            _spec("bearer"), "sys", [{"role": "user", "content": "hi"}], 100, 30.0
        )

    assert out == "ok"
    assert captured["headers"]["Authorization"] == "Bearer sk-cp-test123"
    assert "x-api-key" not in captured["headers"]
    assert captured["headers"]["anthropic-version"] == "2023-06-01"


@pytest.fixture
def reload_config(monkeypatch):
    """Reimport config with controlled env so per-test settings stick."""
    import config as _config

    def _reload(env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", env.get("JWT_SECRET", "x" * 64))
        monkeypatch.delenv("DATABASE_URL", raising=False)
        return importlib.reload(_config)

    return _reload


def test_config_default_auth_style_is_x_api_key(reload_config):
    cfg = reload_config({"MINIMAX_API_KEY": "regular-key"})
    assert cfg.MINIMAX_AUTH_STYLE == "x-api-key"


def test_config_explicit_bearer_overrides_default(reload_config):
    cfg = reload_config({"MINIMAX_API_KEY": "regular-key", "MINIMAX_AUTH_STYLE": "bearer"})
    assert cfg.MINIMAX_AUTH_STYLE == "bearer"


def test_config_sk_cp_prefix_forces_bearer(reload_config):
    cfg = reload_config({"MINIMAX_API_KEY": "sk-cp-abc123"})
    assert cfg.MINIMAX_AUTH_STYLE == "bearer"


def test_config_sk_cp_prefix_overrides_explicit_x_api_key(reload_config):
    """User mistakenly sets MINIMAX_AUTH_STYLE=x-api-key but pasted a
    Coding-Plan key — auto-detect wins (the wrong header would 401)."""
    cfg = reload_config({"MINIMAX_API_KEY": "sk-cp-abc123", "MINIMAX_AUTH_STYLE": "x-api-key"})
    assert cfg.MINIMAX_AUTH_STYLE == "bearer"


def test_config_unknown_auth_style_falls_back_safe(reload_config):
    """Typos like MINIMAX_AUTH_STYLE=bear should not crash module import."""
    cfg = reload_config({"MINIMAX_API_KEY": "k", "MINIMAX_AUTH_STYLE": "bear"})
    assert cfg.MINIMAX_AUTH_STYLE == "x-api-key"
