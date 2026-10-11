"""Optimized-program loading tests (feature 006, T013; research.md D4).

The newly compiled `app/ai/optimized_program.json` (DSPy 3.4.0) must load
into a freshly constructed QueryProgram and carry demonstrations on its
predictors. This guards the silent-fallback risk in `app/api/routes.py`
(`_make_query_program` swallows load errors and falls back to the base
program), which would otherwise mask a stale or incompatible artifact.
"""
from __future__ import annotations

import os

from app.ai.query_program import QueryProgram

OPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "app", "ai", "optimized_program.json")


def test_optimized_program_loads_with_demonstrations():
    assert os.path.exists(OPT_PATH), "optimized program artifact missing"
    program = QueryProgram()
    program.load(OPT_PATH)  # must not raise (routes.py would swallow it)

    plan_demos = getattr(program.plan, "demos", None) or []
    assert len(plan_demos) > 0, (
        "loaded optimized program carries no plan demonstrations — "
        "the artifact is stale or did not round-trip on this DSPy version")
