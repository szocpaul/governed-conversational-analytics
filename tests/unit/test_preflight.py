"""Preflight artifact metadata tests (feature 006, T004).

The preflight record must capture the DSPy version so the artifact proves
which runtime produced it (contract: artifacts/llm-preflight.json records
DSPy 3.4.0).
"""
from __future__ import annotations

import dspy

from app.ai import preflight


def test_preflight_record_includes_dspy_version(monkeypatch):
    """run_preflight must record the installed DSPy version in the record."""

    class _Cfg:
        provider = "openai-compatible"
        base_url = "http://example.invalid"
        model = "m"
        api_key = "k"
        temperature = 0.0
        cache = False

    # Force the endpoint checks to fail fast; we only assert the version
    # field is populated regardless of check outcome.
    monkeypatch.setattr(preflight, "list_models",
                        lambda *a, **k: (_ for _ in ()).throw(
                            preflight.LLMEndpointError("boom")))

    record = preflight.run_preflight(_Cfg())
    assert record["ok"] is False
    assert record["dspy_version"] == dspy.__version__
