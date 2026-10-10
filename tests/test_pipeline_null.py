"""Missing-value filtering pipeline tests (spec 005, T009).

is_null/is_not_null end-to-end with a mocked GraphJin: filtered count and
list requests, "open tickets" = closed_at is_null mapping, and presence
filtering via is_not_null. The schema, validator, builder, and normalization
under test are real.
"""
from __future__ import annotations

import dspy
from fastapi.testclient import TestClient

from app.api import routes
from app.api.schemas import StructuredQueryRequest
from app.data.graphjin_client import build_graphql
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


def test_is_null_count_end_to_end(monkeypatch):
    plan = dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "assigned_agent_id", "op": "is_null",
                  "value": None}],
        limit=100)
    raw = {"data": {"tickets_aggregate": {"aggregate": {"count": 250}}}}
    app, mock = _app(monkeypatch, plan, raw,
                     "250 tickets have no assigned agent.")
    client = TestClient(app)
    resp = client.post(
        "/query", json={"question": "How many tickets have no assigned agent?"})
    body = resp.json()
    assert body["status"] == "answered"
    assert "250" in body["answer"]
    assert body["evidence"]["aggregate"]["count"] == 250
    assert "assigned_agent_id: {is_null: true}" in mock.executed_queries[0]


def test_open_tickets_oldest_list_end_to_end(monkeypatch):
    # "Open" = closed_at is_null (spec FR-010); oldest = created_at asc.
    plan = dict(
        entity="tickets", operation="list",
        fields=["ticket_id", "created_at", "closed_at"],
        filters=[{"field": "closed_at", "op": "is_null", "value": None}],
        order_by="created_at", order_dir="asc", limit=5)
    raw = {"data": {"tickets": [
        {"ticket_id": 849061, "created_at": "2026-06-29T00:25:03+00:00",
         "closed_at": None},
        {"ticket_id": 849229, "created_at": "2026-06-29T00:47:32+00:00",
         "closed_at": None},
        {"ticket_id": 849153, "created_at": "2026-06-29T01:12:11+00:00",
         "closed_at": None},
        {"ticket_id": 849310, "created_at": "2026-06-29T01:30:45+00:00",
         "closed_at": None},
        {"ticket_id": 849402, "created_at": "2026-06-29T02:05:19+00:00",
         "closed_at": None},
    ]}}
    app, mock = _app(monkeypatch, plan, raw,
                     "The 5 oldest open tickets are 849061, 849229, 849153, "
                     "849310 and 849402.")
    client = TestClient(app)
    resp = client.post(
        "/query", json={"question": "List the 5 oldest open tickets"})
    body = resp.json()
    assert body["status"] == "answered"
    rows = body["evidence"]["rows"]
    assert len(rows) == 5
    assert all(r["closed_at"] is None for r in rows)
    q = mock.executed_queries[0]
    assert "closed_at: {is_null: true}" in q
    assert "order_by: {created_at: asc}" in q
    assert "limit: 5" in q


def test_is_not_null_presence_filter_end_to_end(monkeypatch):
    # "Tickets that have been closed" = closed_at is_not_null.
    plan = dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "closed_at", "op": "is_not_null", "value": None}],
        limit=100)
    raw = {"data": {"tickets_aggregate": {"aggregate": {"count": 1807}}}}
    app, mock = _app(monkeypatch, plan, raw,
                     "1807 tickets have been closed.")
    client = TestClient(app)
    resp = client.post(
        "/query", json={"question": "How many tickets have been closed?"})
    body = resp.json()
    assert body["status"] == "answered"
    assert "1807" in body["answer"]
    assert "closed_at: {is_null: false}" in mock.executed_queries[0]


def test_is_null_combined_with_group_by(monkeypatch):
    # Composition (spec edge case): open tickets per category.
    plan = dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"],
        filters=[{"field": "closed_at", "op": "is_null", "value": None}],
        order_by="count", order_dir="desc", limit=100)
    raw = {"data": {"tickets": [
        {"category": "Payments & Checkout", "count_ticket_id": 120},
        {"category": "API Integrations", "count_ticket_id": 110},
    ]}}
    app, mock = _app(monkeypatch, plan, raw,
                     "Payments & Checkout has 120 open tickets.")
    client = TestClient(app)
    resp = client.post(
        "/query", json={"question": "Open tickets per category?"})
    body = resp.json()
    assert body["status"] == "answered"
    q = mock.executed_queries[0]
    assert "closed_at: {is_null: true}" in q
    assert "distinct: [category]" in q
    assert body["evidence"]["rows"][0]["count_ticket_id"] == 120
