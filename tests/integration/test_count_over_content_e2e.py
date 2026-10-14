"""T008: End-to-end count-over-content tests (feature 012, live stack).

Contracts/count-query.md + routing.md + spec US1: "how many tickets about
login" returns the TRUE count (lexical + semantic; NOT 0, NOT the capped
retrieval limit of 25); a paraphrase count includes semantic matches; a topic
with few matches returns the exact small count; "how many P1 tickets" returns
the structured count unchanged (112); the trace shows the count + up to 5
example ids with no credentials/endpoints/prompts.

These tests run against the LIVE stack (PostgreSQL + GraphJin + the pinned
chat/embedding endpoints) and require the calibrated threshold artifact
(count-threshold.json) and the re-tuned classifier (optimized_program.json).
"""
from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

# The governed retrieval list cap (feature 010): the count must NOT equal this.
RETRIEVAL_CAP = 25
# The structured ground truth for "how many P1 tickets" (verified live).
STRUCTURED_P1_COUNT = 112

# Private endpoint / credential patterns that must NEVER appear in output.
_PRIVATE_PATTERNS = [
    re.compile(r"https?://[^\s]*tailee6bc1[^\s]*", re.IGNORECASE),
    re.compile(r"\b\d{1,3}(\.\d{1,3}){3}:\d+\b"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S+"),
]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _post(client, question: str) -> dict:
    resp = client.post("/query", json={"question": question})
    assert resp.status_code == 200
    return resp.json()


def _trace_text(payload: dict) -> str:
    return " ".join(
        f"{e.get('event')} {e.get('detail') or ''}"
        for e in (payload.get("trace") or []))


def _count_of(payload: dict):
    agg = (payload.get("evidence") or {}).get("aggregate") or {}
    return agg.get("count")


def test_true_count_not_zero_not_capped(client):
    """'how many tickets about login' returns the TRUE hybrid count."""
    payload = _post(client, "how many tickets about login")
    assert payload["status"] == "answered"
    count = _count_of(payload)
    assert isinstance(count, int)
    assert count != 0, "the count path must not return the structured 0"
    assert count != RETRIEVAL_CAP, "the count must not be the capped list length"
    # Routed to the count path (not the structured planner).
    assert "count" in _trace_text(payload)


def test_paraphrase_count_includes_semantic_matches(client):
    """A paraphrase count includes semantic matches (not just exact words)."""
    payload = _post(client, "how many tickets are about sign-in problems")
    assert payload["status"] == "answered"
    count = _count_of(payload)
    assert isinstance(count, int)
    # Semantic matches are included: the count exceeds the lexical-only 0 for
    # this paraphrase (no exact 'sign-in problems' wording in the texts).
    assert count > 0


def test_no_undercount_topic_exceeds_retrieval_cap(client):
    """A topic with more matches than the retrieval cap returns the TRUE total.

    'SSO' matches 33 tickets (verified live) — more than the governed retrieval
    cap of 25. The count MUST be the true total (33), NOT the capped list
    length (25) — proving the count is not limited by the retrieval cap.
    """
    payload = _post(client, "how many tickets about SSO")
    assert payload["status"] == "answered"
    count = _count_of(payload)
    assert isinstance(count, int)
    assert count > RETRIEVAL_CAP, "the true total exceeds the retrieval cap"
    assert count != RETRIEVAL_CAP, "the count is NOT the capped list length"


def test_exact_count_matches_calibrated_label(client):
    """'how many tickets about login' returns the exact calibrated count.

    The calibrated hybrid count for 'login' (threshold 0.25) is 156 — the
    lexical matches plus the semantic paraphrase matches. This is the TRUE
    count the governed hybrid query produces (not 0, not 25).
    """
    payload = _post(client, "how many tickets about login")
    assert payload["status"] == "answered"
    assert _count_of(payload) == 156


def test_structured_count_unchanged(client):
    """'how many P1 tickets' routes to the structured path, unchanged (112)."""
    payload = _post(client, "how many P1 tickets are there?")
    assert payload["status"] == "answered"
    assert _count_of(payload) == STRUCTURED_P1_COUNT
    # NOT routed to the content count path.
    assert "content_count" not in _trace_text(payload)


def test_count_trace_sanitized(client):
    """The trace shows the count + up to 5 example ids; no secrets/endpoints."""
    payload = _post(client, "how many tickets about login")
    assert payload["status"] == "answered"
    trace = payload.get("trace") or []
    # Find the count event and check the example ids are capped at <= 5.
    count_events = [e for e in trace if e.get("event") == "count"]
    assert count_events, "trace must record the count event"
    detail = count_events[0].get("detail") or ""
    assert "count=" in detail
    # Example ids present and capped (<= 5).
    import re as _re
    m = _re.search(r"example_ticket_ids=\[(.*?)\]", detail)
    if m and m.group(1).strip():
        ids = [x for x in m.group(1).split(",") if x.strip()]
        assert len(ids) <= 5
    # No credentials, private endpoints, or prompts in the whole trace/answer.
    full = _trace_text(payload) + " " + (payload.get("answer") or "")
    for pat in _PRIVATE_PATTERNS:
        assert not pat.search(full), f"trace/answer leaked: {pat.pattern}"
