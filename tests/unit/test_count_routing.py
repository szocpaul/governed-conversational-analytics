"""T004: Unit tests for content_count routing (feature 012).

Contracts/routing.md + research R4: the extended ClassifyQuestion gains the
content_count category alongside the existing five; "how many tickets about
login" (a COUNT over a TOPIC) routes to the count path (NOT the structured
planner); "how many P1 tickets" (a COUNT over a STRUCTURED value) stays
supported; unparseable/unknown output triggers the conservative fallback to
the structured path. Category parsing uses a stubbed LM (dspy.utils.DummyLM);
the category->path dispatch uses stubbed predictors (house pattern). No live
model, no I/O.
"""
from __future__ import annotations

import dspy
import pytest
from dspy.utils import DummyLM

from app.ai.query_program import QueryProgram
from app.ai.routing import normalize_category
from app.ai.signatures import ClassifyQuestion


# ---------------------------------------------------------------------------
# Category parsing with a stubbed LM: content_count parses alongside the five.
# ---------------------------------------------------------------------------

def _classify_with_dummy(category_text: str) -> str:
    lm = DummyLM([{"category": category_text, "rationale": "r"}])
    with dspy.context(lm=lm):
        pred = dspy.Predict(ClassifyQuestion)(question="q")
    return str(pred.category).strip().lower()


def test_signature_parses_content_count():
    assert _classify_with_dummy("content_count") == "content_count"


@pytest.mark.parametrize("cat", [
    "content_about", "content_similar", "supported", "ambiguous",
    "unsupported", "content_count",
])
def test_signature_parses_all_six_categories(cat):
    assert _classify_with_dummy(cat) == cat


def test_content_count_is_a_known_category():
    assert normalize_category("content_count") == "content_count"


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


def test_count_over_topic_routes_to_count_path_not_planner(monkeypatch):
    # "how many tickets about login" is a COUNT over a TOPIC -> content_count,
    # NOT the structured planner (no structured request is planned).
    prog = _program(
        monkeypatch,
        {"category": "content_count", "rationale": "count over a topic"},
    )
    out = prog(question="how many tickets about login")
    assert out.classification == "content_count"
    assert out.request is None  # no structured request planned


def test_count_over_structured_value_stays_supported(monkeypatch):
    # "how many P1 tickets" is a COUNT over a STRUCTURED value -> supported.
    import json
    plan = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "filters": [{"field": "priority", "op": "eq", "value": "P1"}],
    })
    prog = _program(
        monkeypatch,
        {"category": "supported", "rationale": "structured count"},
        {"request_json": plan},
    )
    out = prog(question="how many P1 tickets are there")
    assert out.classification == "supported"
    assert out.request is not None


def test_list_about_topic_stays_content_about(monkeypatch):
    # A LIST about a topic is content_about (feature 011), not content_count.
    prog = _program(
        monkeypatch,
        {"category": "content_about", "rationale": "list by content"},
    )
    out = prog(question="show me tickets about login")
    assert out.classification == "content_about"
    assert out.request is None


# ---------------------------------------------------------------------------
# Conservative fallback: unparseable/unknown -> structured path.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "count",             # near-miss but not the full category token
    "content_coun",      # truncated
    "gibberish",
    "",
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
