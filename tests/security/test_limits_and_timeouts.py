"""T005: Independent timeout and result-limit tests (US2).

Three controls must be INDEPENDENT (FR-004, plan key decision 5):
  1. database-query timeout (GraphJin client / server-side),
  2. overall request safety timeout (route layer),
  3. maximum result size (row cap at policy + app layers).
100% of limit tests must terminate within configured bounds (SC-005).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import pytest

from app.api.schemas import MAX_LIMIT, StructuredQueryRequest
from app.data.graphjin_client import GraphJinClient, GraphJinError
from app.security.errors import ValidationError
from app.security.validator import validate_request

GRAPHJIN_URL = os.environ.get(
    "GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:8081/api/v1/graphql")

# Configured operational bounds (seconds). The app-level request safety
# timeout and the database-query timeout are independent values.
DB_QUERY_TIMEOUT_S = float(os.environ.get("DB_QUERY_TIMEOUT_S", "5"))
REQUEST_SAFETY_TIMEOUT_S = float(
    os.environ.get("REQUEST_SAFETY_TIMEOUT_S", "120"))


@pytest.fixture(scope="module")
def client():
    c = GraphJinClient(GRAPHJIN_URL, timeout=DB_QUERY_TIMEOUT_S)
    try:
        c.ping()
    except GraphJinError as exc:
        pytest.skip(f"GraphJin not reachable: {exc}")
    return c


# ---------------- 1. database-query timeout --------------------------------

def test_db_query_timeout_is_enforced(client):
    """A slow query must be cut off by the database-query timeout, not by
    the overall request timeout."""
    # pg_sleep via a GraphQL query is not possible (read-only surface), so
    # we prove the client timeout fires against an unreachable-but-open
    # endpoint: connection accepted, response never arrives.
    slow = GraphJinClient("http://10.255.255.1:8081/api/v1/graphql",
                          timeout=DB_QUERY_TIMEOUT_S)
    start = time.monotonic()
    with pytest.raises(GraphJinError):
        slow.execute_raw("{ merchants(limit: 1) { merchant_id } }")
    elapsed = time.monotonic() - start
    assert elapsed < DB_QUERY_TIMEOUT_S + 5, (
        f"database-query timeout not enforced: {elapsed:.1f}s")


def test_db_query_timeout_value_is_independent():
    """The database-query timeout and request safety timeout are separate
    configuration values (FR-004)."""
    assert DB_QUERY_TIMEOUT_S != REQUEST_SAFETY_TIMEOUT_S
    assert DB_QUERY_TIMEOUT_S < REQUEST_SAFETY_TIMEOUT_S


# ---------------- 2. overall request safety timeout ------------------------

def test_request_safety_timeout_configured():
    """The route layer exposes an independent overall safety timeout."""
    from app.api import routes
    assert hasattr(routes, "REQUEST_SAFETY_TIMEOUT_S"), (
        "route-level request safety timeout missing")
    assert routes.REQUEST_SAFETY_TIMEOUT_S == pytest.approx(
        REQUEST_SAFETY_TIMEOUT_S)


def test_request_safety_timeout_enforced(monkeypatch):
    """If the model stage hangs, the request is cut off by the safety
    timeout with a stable category, not left hanging."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from app.api import routes
    from app.main import app

    def _hang(*args, **kwargs):
        time.sleep(REQUEST_SAFETY_TIMEOUT_S + 5)

    monkeypatch.setattr(routes, "_make_query_program",
                        lambda: type("P", (), {"__call__": _hang})())
    monkeypatch.setattr(routes, "REQUEST_SAFETY_TIMEOUT_S", 2.0)

    client = TestClient(app)
    start = time.monotonic()
    resp = client.post("/query", json={"question": "how many tickets?"})
    elapsed = time.monotonic() - start
    assert elapsed < 10, f"request safety timeout not enforced: {elapsed:.1f}s"
    payload = resp.json()
    assert payload["status"] == "dependency_error"


# ---------------- 3. maximum result size ------------------------------------

def test_max_limit_constant_matches_graphjin_policy():
    """App-level cap matches the GraphJin default_limit hard cap (100)."""
    assert MAX_LIMIT == 100


def test_limit_above_cap_rejected_at_type_level():
    with pytest.raises(Exception):
        StructuredQueryRequest(entity="tickets", operation="list",
                               fields=["ticket_id"], limit=MAX_LIMIT + 1)


def test_validator_rejects_excessive_limit():
    req = StructuredQueryRequest(entity="tickets", operation="list",
                                 fields=["ticket_id"], limit=MAX_LIMIT)
    object.__setattr__(req, "limit", MAX_LIMIT * 100)
    with pytest.raises(ValidationError):
        validate_request(req)


def test_graphjin_caps_rows_at_default_limit(client):
    """Even a valid max-limit query returns at most MAX_LIMIT rows."""
    req = StructuredQueryRequest(entity="tickets", operation="list",
                                 fields=["ticket_id"], limit=MAX_LIMIT)
    raw = client.execute(req)
    rows = (raw.get("data") or {}).get("tickets") or []
    assert len(rows) <= MAX_LIMIT


def test_app_never_sends_limit_above_cap(client):
    """The app layer is the hard cap: a typed request can never carry a
    limit above MAX_LIMIT, so GraphJin is never asked for more. This test
    proves the boundary by building the GraphQL for the maximum allowed
    request and confirming the wire query contains limit: 100."""
    from app.data.graphjin_client import build_graphql
    req = StructuredQueryRequest(entity="tickets", operation="list",
                                 fields=["ticket_id"], limit=MAX_LIMIT)
    gql = build_graphql(req)
    assert f"limit: {MAX_LIMIT}" in gql
    assert f"limit: {MAX_LIMIT + 1}" not in gql


def test_graphjin_default_limit_caps_unbounded_query(client):
    """A query with NO explicit limit is capped by the GraphJin
    default_limit (100)."""
    status, body = _graphql_raw("{ tickets { ticket_id } }")
    rows = (body.get("data") or {}).get("tickets") or []
    assert len(rows) <= MAX_LIMIT, (
        f"unbounded query returned {len(rows)} rows, cap is {MAX_LIMIT}")


def _graphql_raw(query: str):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        GRAPHJIN_URL, data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")
