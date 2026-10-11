"""Engine pin tests (007 follow-up): the configured LM must use the native
lm15 backend explicitly, so a future DSPy or environment change cannot
silently fall back to the LiteLLM compatibility engine (3.5 readiness).
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture()
def llm_config():
    from app.ai.llm import LLMConfig

    os.environ.setdefault("LLM_PROVIDER", "openai-compatible")
    os.environ.setdefault("LLM_API_KEY", "local-not-required")
    return LLMConfig.from_env()


def test_configured_lm_pins_lm15_engine(llm_config, monkeypatch):
    """configure_dspy must construct dspy.LM with engine='lm15'."""
    captured = {}

    class _FakeLM:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import dspy

    monkeypatch.setattr(dspy, "LM", _FakeLM)
    monkeypatch.setattr(dspy, "configure", lambda **kw: None)

    from app.ai.llm import configure_dspy

    configure_dspy(llm_config)
    assert captured.get("engine") == "lm15", (
        f"expected engine='lm15' pin, got {captured.get('engine')!r}")


def test_lm15_engine_resolves_native_backend(llm_config):
    """With engine='lm15', backend selection must resolve natively (no
    LiteLLM fallback) for the pinned local endpoint."""
    dspy = pytest.importorskip("dspy")
    from dspy.clients.backend_selection import select_backend

    from app.ai.llm import verify_model

    model = verify_model(llm_config)
    lm = dspy.LM(
        model=f"openai/{model}",
        api_base=llm_config.base_url,
        api_key=llm_config.api_key,
        temperature=0.0,
        cache=False,
        model_type="chat",
        engine="lm15",
    )
    selection = select_backend(lm)
    assert selection.native is True, (
        f"engine='lm15' must resolve to the native backend; got "
        f"native={selection.native}, resolution={selection.resolution}")
