"""Ratio/percentage metric pipeline tests (spec 005, T012).

Global ratio -> expr-aggregate GraphQL -> ratio value in [0, 1] in evidence;
empty base set -> null ratio -> stable clarification (no fabricated number);
ratio per group -> per-group ratio values. GraphJin is mocked; the schema,
validator, builder, normalization, and pipeline are real.
"""
from __future__ import annotations

import dspy
from fastapi.testclient import TestClient

from app.api import routes
from app.api.schemas import StructuredQueryRequest
from app.data.graphjin_client import build_graphql
from app.data.result_normalizer import normalize_result
from app.main import create_app


class _MockGraphJin:
    def __init__(self, raw):
        self.raw = raw
        self.executed_queries: list[str] = []

    def execute(self, req):
        self.executed_queries.append(build_graphql(req))
        return self.raw

    def execute_raw(self, query):
        self.executed_queries.append(query)
        return self.raw


def _app(monkeypatch, plan: dict, raw: dict, answer: str):
    mock = _MockGraphJin(raw)

    class _StubQP:
        def __call__(self, question):
            req = StructuredQueryRequest.model_validate(plan)
            return dspy.Prediction(classification="supported",
                                   rationale="stub", request=req)

    class _StubAP:
        def __call__(self, question, evidence):
            return dspy.Prediction(answer=answer, grounded=True)

    monkeypatch.setattr(routes, "_make_query_program", lambda: _StubQP())
    monkeypatch.setattr(routes, "_make_answer_program", lambda: _StubAP())
    monkeypatch.setattr(routes, "_make_graphjin_client", lambda: mock)
    return create_app(), mock


RATIO_PLAN = dict(
    entity="tickets", operation="aggregate",
    aggregate={"function": "ratio", "field": "resolution_breached"},
    limit=100)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_global_ratio_normalized_to_aggregate():
    req = StructuredQueryRequest.model_validate(RATIO_PLAN)
    raw = {"data": {"tickets": [
        {"ratio_resolution_breached": 0.5041322314049587}]}}
    ev = normalize_result(req, raw)
    assert ev.aggregate is not None
    assert 0.0 <= ev.aggregate["ratio_resolution_breached"] <= 1.0
    assert abs(ev.aggregate["ratio_resolution_breached"] - 0.5041) < 0.001
    assert ev.rows == []


def test_empty_base_set_gives_null_ratio():
    req = StructuredQueryRequest.model_validate(dict(
        RATIO_PLAN,
        filters=[{"field": "priority", "op": "eq", "value": "P9"}]))
    # GraphJin returns null for avg over an empty set (research.md D3).
    raw = {"data": {"tickets": [{"ratio_resolution_breached": None}]}}
    ev = normalize_result(req, raw)
    assert ev.aggregate["ratio_resolution_breached"] is None


def test_ratio_per_group_normalized_to_rows():
    req = StructuredQueryRequest.model_validate(dict(
        RATIO_PLAN, group_by=["category"]))
    raw = {"data": {"tickets": [
        {"category": "API Integrations",
         "ratio_resolution_breached": 0.6981},
        {"category": "Payments & Checkout",
         "ratio_resolution_breached": 0.7930},
    ]}}
    ev = normalize_result(req, raw)
    assert ev.row_count == 2
    assert abs(ev.rows[0]["ratio_resolution_breached"] - 0.6981) < 0.001


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------

def test_global_ratio_end_to_end(monkeypatch):
    raw = {"data": {"tickets": [
        {"ratio_resolution_breached": 0.5041322314049587}]}}
    app, mock = _app(monkeypatch, RATIO_PLAN, raw,
                     "50.4% of tickets breached their resolution SLA.")
    client = TestClient(app)
    resp = client.post(
        "/query",
        json={"question": "What percentage of tickets breached their "
                          "resolution SLA?"})
    body = resp.json()
    assert body["status"] == "answered"
    assert "50.4%" in body["answer"]
    ev = body["evidence"]
    assert abs(ev["aggregate"]["ratio_resolution_breached"] - 0.5041) < 0.001
    # The executed query is the expression aggregate form.
    q = mock.executed_queries[0]
    assert "avg(expr:" in q
    assert "resolution_breached: {eq: true}" in q


def test_zero_denominator_gives_clarification(monkeypatch):
    # Empty base set: ratio is null; the pipeline must NOT fabricate a
    # number — stable clarification instead (FR-004).
    plan = dict(RATIO_PLAN,
                filters=[{"field": "priority", "op": "eq", "value": "P9"}])
    raw = {"data": {"tickets": [{"ratio_resolution_breached": None}]}}
    app, mock = _app(monkeypatch, plan, raw, "unused")
    client = TestClient(app)
    resp = client.post(
        "/query",
        json={"question": "What percentage of P9 tickets breached their "
                          "resolution SLA?"})
    body = resp.json()
    assert body["status"] == "clarification"
    assert "%" not in body["answer"]


def test_ratio_per_group_end_to_end(monkeypatch):
    plan = dict(RATIO_PLAN, group_by=["category"], order_by="category",
                order_dir="asc")
    raw = {"data": {"tickets": [
        {"category": "API Integrations",
         "ratio_resolution_breached": 0.6981},
        {"category": "Payments & Checkout",
         "ratio_resolution_breached": 0.7930},
    ]}}
    app, mock = _app(monkeypatch, plan, raw,
                     "API Integrations: 69.8%; Payments & Checkout: 79.3%.")
    client = TestClient(app)
    resp = client.post(
        "/query",
        json={"question": "What percentage of tickets breached their "
                          "resolution SLA, per category?"})
    body = resp.json()
    assert body["status"] == "answered"
    rows = body["evidence"]["rows"]
    assert len(rows) == 2
    assert abs(rows[0]["ratio_resolution_breached"] - 0.6981) < 0.001
    q = mock.executed_queries[0]
    assert "distinct: [category]" in q
    assert "avg(expr:" in q
