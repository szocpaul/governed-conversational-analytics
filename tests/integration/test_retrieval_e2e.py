"""T020: End-to-end governed retrieval tests (feature 010 US3, live stack).

Through the conversational query path (POST /query): "tickets about login
problems" returns relevant Account Access tickets with a retrieval trace;
"similar to ticket 847203" returns same-category tickets; a structured
question is answered by the structured path exactly as before; a no-match
content query returns a stable clarification; identical retrieval queries
produce identical fused rankings (determinism). Live stack required.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


@pytest.fixture(scope="module")
def client():
    from dotenv import load_dotenv
    load_dotenv()
    os.environ["LLM_TEMPERATURE"] = "0"
    os.environ["LLM_CACHE"] = "false"
    from app.main import app
    with TestClient(app) as c:
        yield c


def _query(client, question):
    return client.post("/query", json={"question": question}).json()


def _rows(payload):
    return (payload.get("evidence") or {}).get("rows") or []


def test_tickets_about_login_problems_returns_account_access(client):
    p = _query(client, "Show me tickets about login problems")
    assert p["status"] == "answered"
    rows = _rows(p)
    assert rows, "expected ranked tickets"
    # Semantic match: login ~ authentication/SSO/password -> Account Access.
    categories = {r.get("category") for r in rows}
    assert "Account Access" in categories
    # Retrieval trace lists exactly the ticket_ids that entered the context.
    retrieval_events = [e for e in p["trace"] if e["event"] == "retrieval"]
    assert retrieval_events, "expected a retrieval trace event"


def test_similar_to_ticket_returns_same_category(client):
    p = _query(client, "Find tickets similar to ticket 847203")
    assert p["status"] == "answered"
    rows = _rows(p)
    assert rows, "expected similar tickets"
    # Ticket 847203 is Account Access / SSO Failure; similar tickets favor it.
    categories = [r.get("category") for r in rows]
    assert categories.count("Account Access") >= len(categories) / 2
    # The reference ticket is never returned as "similar to itself".
    assert 847203 not in [r.get("ticket_id") for r in rows]


def test_structured_question_unchanged(client):
    p = _query(client, "How many P1 tickets are there?")
    assert p["status"] == "answered"
    assert "112" in p["answer"]
    # Structured path: validated + executed via GraphJin, no retrieval event.
    events = {e["event"] for e in p["trace"]}
    assert "executed" in events
    assert "retrieval" not in events


def test_no_match_content_query_returns_stable_clarification(client):
    p = _query(client, "Show me tickets about zqxwvukjnonexistenttopic")
    # Stable clarification or refusal; never a fabricated answer.
    assert p["status"] in ("clarification", "unsupported")


def test_identical_retrieval_queries_identical_ranking(client):
    a = _query(client, "Show me tickets about login problems")
    b = _query(client, "Show me tickets about login problems")
    ids_a = [r.get("ticket_id") for r in _rows(a)]
    ids_b = [r.get("ticket_id") for r in _rows(b)]
    assert ids_a == ids_b and ids_a
