"""Unit tests for the extended routing classifier (T004).

The extended ClassifyQuestion routes every question via ONE classifier with
five categories: content_about, content_similar, supported, ambiguous,
unsupported. Unparseable/unknown output triggers the conservative fallback to
the structured path. Content categories route to the retrieval dispatch (NOT
the structured planner); supported routes to the structured planner unchanged.

Category parsing is tested with a stubbed LM (dspy.utils.DummyLM); the
category->path dispatch is tested with stubbed predictors (house pattern).
No live model, no I/O.
"""
from __future__ import annotations

import dspy
import pytest
from dspy.utils import DummyLM

from app.ai.query_program import QueryProgram
from app.ai.signatures import ClassifyQuestion


# ---------------------------------------------------------------------------
# Category parsing with a stubbed LM (DummyLM): all five categories parse.
# ---------------------------------------------------------------------------

def _classify_with_dummy(category_text: str) -> str:
    lm = DummyLM([{"category": category_text, "rationale": "r"}])
    with dspy.context(lm=lm):
        pred = dspy.Predict(ClassifyQuestion)(question="q")
    return str(pred.category).strip().lower()


@pytest.mark.parametrize("cat", [
    "content_about", "content_similar", "supported", "ambiguous",
    "unsupported",
])
def test_signature_parses_all_five_categories(cat):
    assert _classify_with_dummy(cat) == cat


# ---------------------------------------------------------------------------
# Category -> path dispatch (stubbed predictors; house pattern).
# ---------------------------------------------------------------------------

class _Stub:
    def __init__(self, **kw):
        self._kw = kw

    def __call__(self, **kwargs):
        return dspy.Prediction(**self._kw)


def _program(monkeypatch, classify_out, plan_out=None):
    prog = QueryProgram()
    monkeypatch.setattr(prog, "classify", _Stub(**classify_out))
    if plan_out is not None:
        monkeypatch.setattr(prog, "plan", _Stub(**plan_out))
    return prog


def test_content_about_routes_to_retrieval_not_planner(monkeypatch):
    # content_about must NOT invoke the structured planner; it routes to the
    # retrieval dispatch (classification carries the content mode).
    prog = _program(
        monkeypatch,
        {"category": "content_about", "rationale": "find by content"},
    )
    out = prog(question="customers unable to complete a purchase")
    assert out.classification == "content_about"
    assert out.request is None  # no structured request planned


def test_content_similar_routes_to_retrieval(monkeypatch):
    prog = _program(
        monkeypatch,
        {"category": "content_similar", "rationale": "similar to a ticket"},
    )
    out = prog(question="tickets similar to 847207")
    assert out.classification == "content_similar"
    assert out.request is None


def test_supported_routes_to_structured_planner(monkeypatch):
    import json
    plan = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
    })
    prog = _program(
        monkeypatch,
        {"category": "supported", "rationale": "count"},
        {"request_json": plan},
    )
    out = prog(question="how many tickets")
    assert out.classification == "supported"
    assert out.request is not None


def test_ambiguous_routes_to_clarification(monkeypatch):
    prog = _program(monkeypatch,
                    {"category": "ambiguous", "rationale": "unclear"})
    out = prog(question="show me stuff")
    assert out.classification == "ambiguous"
    assert out.request is None


def test_unsupported_routes_to_refusal(monkeypatch):
    prog = _program(monkeypatch,
                    {"category": "unsupported", "rationale": "out of scope"})
    out = prog(question="what is the weather")
    assert out.classification == "unsupported"
    assert out.request is None


# ---------------------------------------------------------------------------
# Conservative fallback: unparseable/unknown -> structured path.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "content",           # near-miss but not a known category
    "gibberish",
    "",
    "similar",           # not the full category token
    "content_abou",      # truncated
])
def test_unknown_category_falls_back_to_structured(monkeypatch, bad):
    import json
    plan = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
    })
    prog = _program(
        monkeypatch,
        {"category": bad, "rationale": "x"},
        {"request_json": plan},
    )
    out = prog(question="how many tickets about login")
    # Conservative fallback: unknown -> treated as supported (structured).
    assert out.classification == "supported"


def test_case_and_whitespace_normalize_to_valid_category(monkeypatch):
    # Robust parsing: case/whitespace variants of a known category are
    # normalized and accepted (NOT treated as uncertain).
    prog = _program(
        monkeypatch,
        {"category": "  Content_About  ", "rationale": "x"},
    )
    out = prog(question="find tickets by content")
    assert out.classification == "content_about"
    assert out.request is None
