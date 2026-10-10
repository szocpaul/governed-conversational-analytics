"""End-to-end grouped aggregation pipeline tests (spec 005, T005/T006).

GraphJin is mocked at the client level so the tests are deterministic and
offline; the schema, validator, GraphQL builder, evidence normalization,
having post-filter, and grounding under test are real.
"""
from __future__ import annotations

import json

import dspy
import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.api.schemas import Evidence, StructuredQueryRequest
from app.data.graphjin_client import build_graphql
from app.data.result_normalizer import normalize_result
from app.main import create_app

GROUPED_RAW = {
    "data": {
        "tickets": [
            {"category": "Payments & Checkout", "count_ticket_id": 483},
            {"category": "API Integrations", "count_ticket_id": 477},
            {"category": "Notifications", "count_ticket_id": 374},
        ]
    }
}


class _MockGraphJin:
    """Records the executed query and returns a canned governed response."""

    def __init__(self, raw):
        self.raw = raw
        self.executed_queries: list[str] = []

    def execute(self, req):
        self.executed_queries.append(build_graphql(req))
        return self.raw

    def execute_raw(self, query):
        self.executed_queries.append(query)
        return self.raw


def _app(monkeypatch, plan: dict, raw: dict, answer: str | None = None):
    mock = _MockGraphJin(raw)

    class _StubQP:
        def __call__(self, question):
            req = StructuredQueryRequest.model_validate(plan)
            return dspy.Prediction(classification="supported",
                                   rationale="stub", request=req)

    class _StubAP:
        def __call__(self, question, evidence):
            if answer is not None:
                return dspy.Prediction(answer=answer, grounded=True)
            # Default: echo the first group row.
            if evidence.rows:
                r = evidence.rows[0]
                return dspy.Prediction(
                    answer=f"{r.get('category')} has "
                           f"{r.get('count_ticket_id')} tickets.",
                    grounded=True)
            return dspy.Prediction(answer="No matching data was found.",
                                   grounded=True)

    monkeypatch.setattr(routes, "_make_query_program", lambda: _StubQP())
    monkeypatch.setattr(routes, "_make_answer_program", lambda: _StubAP())
    monkeypatch.setattr(routes, "_make_graphjin_client", lambda: mock)
    return create_app(), mock


# ---------------------------------------------------------------------------
# Grouped evidence normalization (T005)
# ---------------------------------------------------------------------------

def test_grouped_result_normalized_to_rows():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"], order_by="count", order_dir="desc"))
    ev = normalize_result(req, GROUPED_RAW)
    assert ev.row_count == 3
    assert ev.rows[0] == {"category": "Payments & Checkout",
                          "count_ticket_id": 483}
    assert ev.aggregate is None


def test_grouped_evidence_marks_truncation_at_limit():
    # When the number of returned groups equals the request limit, the
    # result may be truncated: evidence must say so (spec edge case).
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"], limit=3))
    ev = normalize_result(req, GROUPED_RAW)
    assert ev.groups_truncated is True


def test_grouped_evidence_not_truncated_below_limit():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"], limit=100))
    ev = normalize_result(req, GROUPED_RAW)
    assert ev.groups_truncated is False


def test_order_by_count_maps_to_aggregate_column_in_query():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"], order_by="count", order_dir="desc"))
    q = build_graphql(req)
    assert "order_by: {count_ticket_id: desc}" in q


# ---------------------------------------------------------------------------
# End-to-end grouped pipeline (T005)
# ---------------------------------------------------------------------------

def test_grouped_pipeline_end_to_end(monkeypatch):
    plan = dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"], order_by="count", order_dir="desc",
        limit=100)
    app, mock = _app(monkeypatch, plan, GROUPED_RAW)
    client = TestClient(app)
    resp = client.post("/query",
                       json={"question": "Which category has the most tickets?"})
    body = resp.json()
    assert body["status"] == "answered"
    assert "Payments & Checkout" in body["answer"]
    assert "483" in body["answer"]
    # Executed query is the grouped GraphQL form.
    assert mock.executed_queries
    assert "distinct: [category]" in mock.executed_queries[0]
    # Evidence carries the per-group rows.
    ev = body["evidence"]
    assert ev["rows"][0]["category"] == "Payments & Checkout"
    assert ev["rows"][0]["count_ticket_id"] == 483
    assert ev["groups_truncated"] is False


def test_grouped_pipeline_truncation_flag_in_evidence(monkeypatch):
    plan = dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"], order_by="count", order_dir="desc", limit=3)
    app, mock = _app(monkeypatch, plan, GROUPED_RAW)
    client = TestClient(app)
    resp = client.post("/query",
                       json={"question": "Which category has the most tickets?"})
    body = resp.json()
    assert body["evidence"]["groups_truncated"] is True


# ---------------------------------------------------------------------------
# Having post-filter (T006)
# ---------------------------------------------------------------------------

MERCHANT_GROUPS = {
    "data": {
        "tickets": [
            {"merchant_id": 101, "count_ticket_id": 87},
            {"merchant_id": 102, "count_ticket_id": 51},
            {"merchant_id": 103, "count_ticket_id": 12},
            {"merchant_id": 104, "count_ticket_id": 3},
        ]
    }
}

HAVING_PLAN = dict(
    entity="tickets", operation="aggregate",
    aggregate={"function": "count", "field": None},
    group_by=["merchant_id"],
    having={"function": "count", "field": None, "op": "gt", "value": 50},
    order_by="count", order_dir="desc", limit=100)


def test_having_drops_groups_below_threshold(monkeypatch):
    app, mock = _app(monkeypatch, HAVING_PLAN, MERCHANT_GROUPS,
                     answer="2 merchants have more than 50 tickets: "
                            "101 (87) and 102 (51).")
    client = TestClient(app)
    resp = client.post(
        "/query", json={"question": "Which merchants have more than 50 tickets?"})
    body = resp.json()
    assert body["status"] == "answered"
    ev = body["evidence"]
    # Only groups with count > 50 remain.
    assert [r["merchant_id"] for r in ev["rows"]] == [101, 102]
    # The post-filter is recorded for traceability.
    ha = ev["having_applied"]
    assert ha["function"] == "count"
    assert ha["op"] == "gt"
    assert ha["value"] == 50
    assert ha["groups_dropped"] == 2


def test_having_not_sent_to_graphjin(monkeypatch):
    app, mock = _app(monkeypatch, HAVING_PLAN, MERCHANT_GROUPS,
                     answer="2 merchants.")
    client = TestClient(app)
    client.post("/query",
                json={"question": "Which merchants have more than 50 tickets?"})
    # GraphJin v3 has no HAVING: the executed query must not contain it.
    assert mock.executed_queries
    assert "having" not in mock.executed_queries[0]


def test_having_zero_groups_left_gives_clarification(monkeypatch):
    plan = dict(HAVING_PLAN)
    plan["having"] = {"function": "count", "field": None, "op": "gt",
                      "value": 1000}
    app, mock = _app(monkeypatch, plan, MERCHANT_GROUPS)
    client = TestClient(app)
    resp = client.post(
        "/query", json={"question": "Which merchants have more than 1000 tickets?"})
    body = resp.json()
    # Zero groups after the post-filter: stable clarification, no invented
    # numbers.
    assert body["status"] == "clarification"
    assert body["evidence"]["having_applied"]["groups_dropped"] == 4


def test_having_avg_function_post_filter(monkeypatch):
    raw = {"data": {"tickets": [
        {"category": "A", "avg_resolution_hours": 45.5},
        {"category": "B", "avg_resolution_hours": 10.0},
    ]}}
    plan = dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "avg", "field": "resolution_hours"},
        group_by=["category"],
        having={"function": "avg", "field": "resolution_hours", "op": "gte",
                "value": 30},
        limit=100)
    app, mock = _app(monkeypatch, plan, raw,
                     answer="Category A averages 45.5 hours.")
    client = TestClient(app)
    resp = client.post(
        "/query",
        json={"question": "Which categories average at least 30 resolution hours?"})
    body = resp.json()
    assert body["status"] == "answered"
    assert [r["category"] for r in body["evidence"]["rows"]] == ["A"]
    assert body["evidence"]["having_applied"]["groups_dropped"] == 1
