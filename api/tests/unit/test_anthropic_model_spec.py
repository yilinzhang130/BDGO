"""Unit tests for the Anthropic Claude model spec (P1-07).

Verifies that the ``claude-sonnet`` entry in the model registry is
correctly configured for the native Anthropic Messages API so that
the streaming path works without any provider-specific code changes.

Key invariants:
  1. Registry contains ``claude-sonnet``.
  2. Provider is ``"anthropic"`` and auth style is ``"x-api-key"``
     (Anthropic's standard header; NOT bearer like MiniMax Coding Plan keys).
  3. ``anthropic-version`` header is set (required by the API).
  4. API URL points to the official Anthropic endpoint.
  5. ``available_models()`` exposes ``available: False`` when the key is
     absent and ``available: True`` when it is present.
  6. ``resolve_model("claude-sonnet")`` returns the spec; unknown IDs
     fall back to the default without raising.
  7. ``fallback_chain`` never includes the model being tried.
  8. Credit weights are higher than MiniMax baseline (Claude costs more).
"""

from __future__ import annotations

from unittest.mock import patch


def _models_mod():
    """Re-import models after patching config values."""
    import models as m

    return m


# ─────────────────────────────────────────────────────────────
# Registry presence
# ─────────────────────────────────────────────────────────────


def test_claude_sonnet_in_registry():
    from models import MODELS

    assert "claude-sonnet" in MODELS


def test_claude_sonnet_provider():
    from models import MODELS

    assert MODELS["claude-sonnet"].provider == "anthropic"


def test_claude_sonnet_api_url():
    from models import MODELS

    spec = MODELS["claude-sonnet"]
    assert spec.api_url == "https://api.anthropic.com/v1/messages"


def test_claude_sonnet_auth_style_is_x_api_key():
    """Anthropic uses `x-api-key`, NOT bearer."""
    from models import MODELS

    assert MODELS["claude-sonnet"].auth_style == "x-api-key"


def test_claude_sonnet_anthropic_version_set():
    """The `anthropic-version` header is required; must not be None or empty."""
    from models import MODELS

    v = MODELS["claude-sonnet"].anthropic_version
    assert v and v.startswith("2023"), f"unexpected anthropic_version: {v!r}"


def test_claude_sonnet_api_model_is_versioned():
    """api_model must be a concrete versioned identifier, not a bare family name.

    Bare names like ``claude-sonnet-4`` are not valid API model identifiers;
    they need a minor version (e.g. ``claude-sonnet-4-5``).
    """
    from models import MODELS

    api_model = MODELS["claude-sonnet"].api_model
    # Must contain at least two numeric parts (major-minor or date YYYYMMDD)
    parts = api_model.replace("-", " ").split()
    numeric_parts = [p for p in parts if p.isdigit() or (len(p) == 8 and p.isdigit())]
    assert len(numeric_parts) >= 2, (
        f"api_model={api_model!r} looks like a bare family name — use a versioned identifier "
        "(e.g. 'claude-sonnet-4-5')"
    )


def test_claude_sonnet_context_note():
    from models import MODELS

    assert "200k" in MODELS["claude-sonnet"].context_note


def test_claude_sonnet_credit_weights_higher_than_minimax():
    """Claude is more expensive than MiniMax baseline."""
    from models import MODELS

    claude = MODELS["claude-sonnet"]
    minimax = MODELS["minimax-m1"]
    assert claude.input_weight > minimax.input_weight
    assert claude.output_weight > minimax.output_weight


# ─────────────────────────────────────────────────────────────
# available_models() visibility
# ─────────────────────────────────────────────────────────────


def test_available_models_includes_claude():
    from models import available_models

    ids = [m["id"] for m in available_models()]
    assert "claude-sonnet" in ids


def test_available_models_claude_unavailable_without_key():
    """When CLAUDE_API_KEY is absent the UI should show the model as locked."""
    import dataclasses

    import models as models_mod

    original = models_mod.MODELS["claude-sonnet"]
    no_key = dataclasses.replace(original, api_key="")
    with patch.dict(models_mod.MODELS, {"claude-sonnet": no_key}):
        # Also patch _MODELS so available_models() iterates the right list
        patched_list = [no_key if m.id == "claude-sonnet" else m for m in models_mod._MODELS]
        with patch.object(models_mod, "_MODELS", patched_list):
            result = {m["id"]: m for m in models_mod.available_models()}
    assert result["claude-sonnet"]["available"] is False


def test_available_models_claude_available_with_key():
    import dataclasses

    import models as models_mod

    original = models_mod.MODELS["claude-sonnet"]
    with_key = dataclasses.replace(original, api_key="sk-ant-test123")
    patched_list = [with_key if m.id == "claude-sonnet" else m for m in models_mod._MODELS]
    with patch.object(models_mod, "_MODELS", patched_list):
        result = {m["id"]: m for m in models_mod.available_models()}
    assert result["claude-sonnet"]["available"] is True


def test_available_models_shape():
    from models import available_models

    for entry in available_models():
        assert "id" in entry
        assert "display_name" in entry
        assert "provider" in entry
        assert "available" in entry


# ─────────────────────────────────────────────────────────────
# resolve_model
# ─────────────────────────────────────────────────────────────


def test_resolve_model_claude_sonnet():
    from models import MODELS, resolve_model

    assert resolve_model("claude-sonnet") is MODELS["claude-sonnet"]


def test_resolve_model_unknown_falls_back_to_default():
    from models import DEFAULT_MODEL_ID, MODELS, resolve_model

    spec = resolve_model("does-not-exist")
    assert spec is MODELS[DEFAULT_MODEL_ID]


def test_resolve_model_none_falls_back_to_default():
    from models import DEFAULT_MODEL_ID, MODELS, resolve_model

    assert resolve_model(None) is MODELS[DEFAULT_MODEL_ID]


# ─────────────────────────────────────────────────────────────
# fallback_chain
# ─────────────────────────────────────────────────────────────


def test_fallback_chain_excludes_self():
    import dataclasses

    import models as models_mod

    original = models_mod.MODELS["claude-sonnet"]
    with_key = dataclasses.replace(original, api_key="sk-ant-test")
    with patch.dict(models_mod.MODELS, {"claude-sonnet": with_key}):
        chain = models_mod.fallback_chain("claude-sonnet")
    ids = [m.id for m in chain]
    assert "claude-sonnet" not in ids


def test_fallback_chain_excludes_models_with_no_key():
    import dataclasses

    import models as models_mod

    original = models_mod.MODELS["claude-sonnet"]
    no_key = dataclasses.replace(original, api_key="")
    with patch.dict(models_mod.MODELS, {"claude-sonnet": no_key}):
        chain = models_mod.fallback_chain("minimax-m1")
    ids = [m.id for m in chain]
    assert "claude-sonnet" not in ids


def test_fallback_chain_includes_claude_when_key_present():
    import dataclasses

    import models as models_mod

    original = models_mod.MODELS["claude-sonnet"]
    with_key = dataclasses.replace(original, api_key="sk-ant-test")
    with patch.dict(models_mod.MODELS, {"claude-sonnet": with_key}):
        chain = models_mod.fallback_chain("minimax-m1")
    ids = [m.id for m in chain]
    assert "claude-sonnet" in ids
