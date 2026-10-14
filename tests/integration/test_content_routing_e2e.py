"""T008: End-to-end content routing tests (feature 011 US1, live stack).

Through the conversational query path (POST /query), the tuned ClassifyQuestion
routes content questions — including DEEP PARAPHRASES with zero shared
keywords — to governed retrieval, while structured analytical questions route
to the structured path unchanged and unsupported questions are refused.

Live stack required (PostgreSQL + GraphJin + the pinned chat/embedding
endpoints). The classifier is the real pinned model (temperature 0, cache
disabled); retrieval is the governed feature 010 channel.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


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


def _events(payload):
    return {e["event"] for e in payload.get("trace") or []}


def _retrieval_mode(payload):
    for e in payload.get("trace") or []:
        if e["event"] == "retrieval":
            # detail like "mode=about ticket_ids=[...]"
            detail = e.get("detail", "")
            if "mode=about" in detail:
                return "about"
            if "mode=similar" in detail:
                return "similar"
    return None


# ---------------------------------------------------------------------------
# Deep paraphrase content questions -> governed retrieval (the core fix)
# ---------------------------------------------------------------------------

def test_deep_paraphrase_card_rejected_routes_to_retrieval(client):
    # Zero shared keywords with the tickets; the OLD regex router missed this.
    p = _query(client, "Which tickets describe customers unable to complete "
                       "a purchase because their card was rejected?")
    assert p["status"] == "answered"
    assert _retrieval_mode(p) == "about"
    rows = _rows(p)
    assert rows, "expected ranked tickets from retrieval"
    categories = {r.get("category") for r in rows}
    assert "Payments & Checkout" in categories


def test_deep_paraphrase_locked_out_routes_to_retrieval(client):
    p = _query(client, "show me cases where people get locked out and can't "
                       "prove who they are at sign-in")
    assert p["status"] == "answered"
    assert _retrieval_mode(p) == "about"
    rows = _rows(p)
    assert rows
    categories = {r.get("category") for r in rows}
    assert "Account Access" in categories


def test_similar_question_routes_to_retrieval_similar_mode(client):
    p = _query(client, "tickets similar to 847207")
    assert p["status"] == "answered"
    assert _retrieval_mode(p) == "similar"
    rows = _rows(p)
    assert rows, "expected similar tickets"
    # Ticket 847207 is Payments & Checkout; similar tickets favor it.
    categories = [r.get("category") for r in rows]
    assert categories.count("Payments & Checkout") >= 1
    # The reference ticket is never returned as similar to itself.
    assert 847207 not in [r.get("ticket_id") for r in rows]


# ---------------------------------------------------------------------------
# Structured analytical questions -> structured path UNCHANGED (no retrieval)
# ---------------------------------------------------------------------------

def test_count_about_a_topic_stays_structured(client):
    # "how many tickets about login" is a COUNT -> structured, NOT retrieval.
    p = _query(client, "how many tickets are about login")
    assert p["status"] == "answered"
    events = _events(p)
    assert "executed" in events, "expected the structured GraphJin path"
    assert "retrieval" not in events, "a count must not route to retrieval"


def test_structured_count_unchanged(client):
    p = _query(client, "How many P1 tickets are there?")
    assert p["status"] == "answered"
    assert "112" in p["answer"]
    events = _events(p)
    assert "executed" in events
    assert "retrieval" not in events


# ---------------------------------------------------------------------------
# Unsupported / out-of-scope -> stable refusal
# ---------------------------------------------------------------------------

def test_unsupported_question_refused(client):
    p = _query(client, "What is the weather forecast for tomorrow?")
    assert p["status"] in ("unsupported", "clarification")
    events = _events(p)
    assert "retrieval" not in events
    assert "executed" not in events
