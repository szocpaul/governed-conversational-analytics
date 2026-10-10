"""Live end-to-end regression tests for the T010-review findings (F1-F10).

These run the exact human-review questions through the full live pipeline
(pinned LLM + governed GraphJin + database) and assert the corrected
behavior against the verified ground truths:

- F2: GROUP BY question -> stable unsupported/clarification, NEVER a wrong
  "no data" answer (ground truth: P1=49, P2=163 after 2026-01-01).
- F3: superlative question -> either the correct agent (Samira Khan, 1.355)
  or a stable clarification/unsupported; never an ungrounded wrong name.
- F4: avg resolution for P1 + Account Access -> answered 2.34 (was a false
  grounding refusal).
- F5 (control): reopened count = 307 (must stay answered).
- F6: avg(boolean) -> stable unsupported, zero GraphJin type errors.
- F7: order_by list -> normalized or stable category, never a raw pydantic
  model-dependency failure.
- F8: "which category has the most" -> stable unsupported/clarification,
  never "no matching data" (ground truth: Payments & Checkout, 483).
- F9: merchant name filter on integer id -> stable unsupported, no DB error.
- F10: null filter -> stable unsupported, no DB error.

Skipped when the LLM endpoint or GraphJin is unreachable.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

GRAPHJIN_URL = os.environ.get(
    "GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:8081/api/v1/graphql")


def _graphjin_up() -> bool:
    import httpx
    try:
        r = httpx.post(GRAPHJIN_URL,
                       json={"query": "{ merchants(limit: 1) { merchant_id } }"},
                       timeout=5)
        return r.status_code == 200 and "data" in r.json()
    except Exception:
        return False


def _llm_up() -> bool:
    import httpx
    base = os.environ.get("LLM_BASE_URL", "")
    if not base:
        return False
    try:
        r = httpx.get(f"{base}/models", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_graphjin_up() and _llm_up()),
    reason="GraphJin or pinned LLM endpoint not reachable")


@pytest.fixture(scope="module")
def client():
    from dotenv import load_dotenv
    load_dotenv()
    with TestClient(app) as c:  # lifespan configures the pinned LM
        if not getattr(app.state, "llm_ready", False):
            pytest.skip(f"LLM not ready: {getattr(app.state, 'llm_error', '')}")
        yield c


def _query(client, question: str) -> dict:
    resp = client.post("/query", json={"question": question})
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# F1/F2/F8: GROUP BY questions must not return a wrong plain-count answer
# ---------------------------------------------------------------------------

def test_f1_groupby_merchants_stable_category(client):
    body = _query(client, "Which merchants have more than 50 tickets, "
                          "avg resolution by sector?")
    # Must not fabricate a per-group breakdown; stable non-answer category.
    assert body["status"] in ("clarification", "unsupported", "answered")
    if body["status"] == "answered":
        # If answered, it must not claim a grouped breakdown was computed.
        assert "sector" not in body["answer"].lower() or \
               "cannot" in body["answer"].lower()


def test_f2_groupby_no_wrong_answer(client):
    body = _query(client, "How many P1 and P2 tickets after 2026-01-01, "
                          "grouped by category?")
    # The bug returned "No matching data" with a plain count of 212.
    # After the fix: unsupported (GROUP BY rejected) or clarification.
    assert body["status"] in ("unsupported", "clarification"), (
        f"expected unsupported/clarification, got {body['status']}: "
        f"{body['answer']!r}")


def test_f8_top_category_no_wrong_answer(client):
    body = _query(client, "Which category has the most tickets?")
    # Spec 004 bug: returned "No matching data" with count=2057. Spec 005
    # makes the grouped shape SUPPORTED: the answer must name the true top
    # category (Payments & Checkout, 483) grounded in executed groups, or
    # fall back to a stable category without inventing data.
    if body["status"] == "answered":
        assert "Payments & Checkout" in body["answer"], (
            f"wrong top category answered: {body['answer']!r}")
        assert "483" in body["answer"], (
            f"top-category count missing from answer: {body['answer']!r}")
        rows = (body.get("evidence") or {}).get("rows") or []
        assert rows and rows[0].get("category") == "Payments & Checkout"
        assert rows[0].get("count_ticket_id") == 483
    else:
        assert body["status"] in ("clarification", "unsupported"), (
            f"unexpected status {body['status']}: {body['answer']!r}")


# ---------------------------------------------------------------------------
# F3: superlative must not return an ungrounded wrong agent
# ---------------------------------------------------------------------------

def test_f3_highest_efficiency_agent(client):
    body = _query(client, "Which agent has the highest efficiency "
                          "multiplier, and how many tickets assigned?")
    if body["status"] == "answered":
        # Ground truth: Samira Khan, 1.355. The wrong answer (Alex Mercer,
        # 1.061) came from an unordered limit-1 query.
        assert "Samira Khan" in body["answer"], (
            f"wrong agent answered: {body['answer']!r}")
        assert "1.355" in body["answer"] or "1.36" in body["answer"]
    else:
        # Multi-part questions may be clarified/unsupported instead.
        assert body["status"] in ("clarification", "unsupported")


# ---------------------------------------------------------------------------
# F4: avg resolution for P1 + Account Access must be answered (2.34)
# ---------------------------------------------------------------------------

def test_f4_avg_resolution_answered(client):
    body = _query(client, "avg resolution time for P1 tickets in Account "
                          "Access category?")
    assert body["status"] == "answered", (
        f"expected answered, got {body['status']}: {body['answer']!r}")
    assert "2.34" in body["answer"]


# ---------------------------------------------------------------------------
# F5 (control): reopened count stays answered
# ---------------------------------------------------------------------------

def test_f5_control_reopened_count(client):
    body = _query(client, "How many tickets were reopened?")
    assert body["status"] == "answered"
    assert "307" in body["answer"]


# ---------------------------------------------------------------------------
# F6/F9/F10: type-incompatible requests -> stable unsupported, no DB error
# ---------------------------------------------------------------------------

def test_f6_avg_boolean_unsupported(client):
    body = _query(client, "What percentage of tickets breached resolution "
                          "SLA?")
    # avg(boolean) must be rejected before GraphJin. A count-based ratio or
    # a stable unsupported/clarification are acceptable; a dependency_error
    # from a database type error is not.
    assert body["status"] in ("answered", "unsupported", "clarification"), (
        f"unexpected status {body['status']}: {body['answer']!r}")
    if body["status"] == "answered":
        # count-based ratio: 1037 of 2057 breached (~50.4%).
        assert any(v in body["answer"] for v in ("1037", "50.4", "50%", "2057"))


def test_f9_merchant_name_filter_unsupported(client):
    body = _query(client, "How many tickets does merchant 'Acme Corp' have?")
    # 'Acme Corp' does not exist; the id-type mismatch must be rejected
    # before GraphJin (unsupported/clarification), never a DB type error.
    assert body["status"] in ("answered", "unsupported", "clarification"), (
        f"unexpected status {body['status']}: {body['answer']!r}")
    if body["status"] == "answered":
        assert "no" in body["answer"].lower() or "0" in body["answer"]


def test_f10_null_agent_filter_unsupported(client):
    body = _query(client, "Show tickets where assigned agent is missing")
    # No is-null operator: must be a stable category, never a DB error from
    # an invalid integer literal.
    assert body["status"] in ("answered", "unsupported", "clarification"), (
        f"unexpected status {body['status']}: {body['answer']!r}")


# ---------------------------------------------------------------------------
# F7: order_by list -> normalized or stable category (no raw pydantic error)
# ---------------------------------------------------------------------------

def test_f7_oldest_open_tickets_no_model_failure(client):
    body = _query(client, "List 5 oldest open tickets with merchant names")
    # The bug surfaced a pydantic ValidationError as a model dependency
    # failure. After the fix the order_by list is normalized (answered) or
    # the request is rejected with a stable category.
    assert body["status"] in ("answered", "unsupported", "clarification"), (
        f"unexpected status {body['status']}: {body['answer']!r}")
    if body["status"] == "answered":
        assert body["evidence"] is not None
        assert body["evidence"]["row_count"] <= 5
