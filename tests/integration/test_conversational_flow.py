"""Integration tests for GraphJin execution and result normalization (T005).

These tests run against the live governed GraphJin surface from spec 001
(127.0.0.1:8081). They prove the typed request -> GraphQL -> normalized
evidence path works end to end and never issues writes.
"""
from __future__ import annotations

import os

import pytest

from app.api.schemas import StructuredQueryRequest
from app.data.graphjin_client import GraphJinClient, GraphJinError
from app.data.result_normalizer import normalize_result

GRAPHJIN_URL = os.environ.get(
    "GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:8081/api/v1/graphql")


def _client() -> GraphJinClient:
    return GraphJinClient(GRAPHJIN_URL, timeout=15.0)


@pytest.fixture(scope="module")
def client():
    c = _client()
    try:
        c.ping()
    except GraphJinError as exc:
        pytest.skip(f"GraphJin not reachable: {exc}")
    return c


def test_ping(client):
    assert client.ping() is True


def test_count_all_tickets(client):
    req = StructuredQueryRequest(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None})
    raw = client.execute(req)
    ev = normalize_result(req, raw)
    assert ev.aggregate is not None
    assert ev.aggregate["count"] == 2057
    assert ev.row_count == 0  # aggregate, not rows


def test_filtered_count(client):
    req = StructuredQueryRequest(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "priority", "op": "eq", "value": "P1"}])
    ev = normalize_result(req, client.execute(req))
    assert ev.aggregate["count"] == 112


def test_list_with_relationship(client):
    req = StructuredQueryRequest(
        entity="tickets", operation="list", fields=["ticket_id"],
        relationships=["merchants"], limit=3)
    ev = normalize_result(req, client.execute(req))
    assert ev.row_count == 3
    assert all("ticket_id" in r for r in ev.rows)
    # relationship key present (may be null when unassigned)
    assert any("merchants" in r for r in ev.rows)


def test_time_filter_count(client):
    req = StructuredQueryRequest(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "created_at", "op": "gte", "value": "2026-01-01"},
                 {"field": "created_at", "op": "lt", "value": "2026-03-01"}])
    ev = normalize_result(req, client.execute(req))
    assert isinstance(ev.aggregate["count"], int)
    assert ev.aggregate["count"] >= 0


def test_avg_aggregate(client):
    req = StructuredQueryRequest(
        entity="tickets", operation="aggregate",
        aggregate={"function": "avg", "field": "resolution_hours"})
    ev = normalize_result(req, client.execute(req))
    assert abs(ev.aggregate["avg_resolution_hours"] - 31.849) < 0.01


def test_empty_result_no_invention(client):
    req = StructuredQueryRequest(
        entity="tickets", operation="list", fields=["ticket_id"],
        filters=[{"field": "priority", "op": "eq", "value": "P9"}])
    ev = normalize_result(req, client.execute(req))
    assert ev.row_count == 0
    assert ev.rows == []


def test_read_only_surface_rejects_mutation(client):
    # The governed surface must reject any mutation attempt.
    with pytest.raises(GraphJinError):
        client.execute_raw(
            'mutation { update_tickets(set: {priority: "P9"}) { ticket_id } }')
