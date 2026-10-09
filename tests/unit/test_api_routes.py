"""API orchestration tests (T007).

Covers the full flow: supported question -> answer+trace+latency, ambiguous ->
clarification (no query), unsupported -> refusal, dependency failure ->
stable error with no fallback. LLM planning is stubbed for determinism except
where marked; GraphJin uses the live governed surface.
"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.api.schemas import StructuredQueryRequest

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


pytestmark = pytest.mark.skipif(not _graphjin_up(),
                                reason="GraphJin not reachable")


def _app_with_stub(monkeypatch, classification, plan_json):
    """Build the app with the DSPy query program stubbed."""
    import dspy
    from app.api import routes

    class _StubQP:
        def __call__(self, question):
            if classification == "supported":
                req = StructuredQueryRequest.model_validate(json.loads(plan_json))
                return dspy.Prediction(classification="supported",
                                       rationale="stub", request=req)
            return dspy.Prediction(classification=classification,
                                   rationale="stub", request=None)

    class _StubAP:
        def __call__(self, question, evidence):
            import json as _json
            agg = evidence.aggregate or {}
            if "count" in agg:
                return dspy.Prediction(answer=f"There are {agg['count']} tickets.",
                                       grounded=True)
            return dspy.Prediction(answer="No matching data was found.",
                                   grounded=True)

    monkeypatch.setattr(routes, "_make_query_program", lambda: _StubQP())
    monkeypatch.setattr(routes, "_make_answer_program", lambda: _StubAP())
    return create_app()


def test_supported_question_answered(monkeypatch):
    plan = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "filters": [{"field": "priority", "op": "eq", "value": "P1"}],
    })
    app = _app_with_stub(monkeypatch, "supported", plan)
    client = TestClient(app)
    resp = client.post("/query", json={"question": "How many P1 tickets?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "answered"
    assert "112" in body["answer"]
    assert body["evidence"]["aggregate"]["count"] == 112
    assert body["latency_ms"] >= 0
    assert len(body["trace"]) >= 1


def test_ambiguous_question_clarification_no_query(monkeypatch):
    app = _app_with_stub(monkeypatch, "ambiguous", "")
    client = TestClient(app)
    resp = client.post("/query", json={"question": "Show me recent stuff"})
    body = resp.json()
    assert body["status"] == "clarification"
    assert body["evidence"] is None


def test_unsupported_question_refusal(monkeypatch):
    app = _app_with_stub(monkeypatch, "unsupported", "")
    client = TestClient(app)
    resp = client.post("/query", json={"question": "What is the weather?"})
    body = resp.json()
    assert body["status"] == "unsupported"
    assert body["evidence"] is None


def test_dependency_failure_no_fallback(monkeypatch):
    plan = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
    })
    app = _app_with_stub(monkeypatch, "supported", plan)
    # Point GraphJin at a dead port to force a dependency failure.
    monkeypatch.setenv("GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:9999/api/v1/graphql")
    app = create_app()
    import dspy
    from app.api import routes

    class _StubQP:
        def __call__(self, question):
            req = StructuredQueryRequest.model_validate(json.loads(plan))
            return dspy.Prediction(classification="supported",
                                   rationale="stub", request=req)

    monkeypatch.setattr(routes, "_make_query_program", lambda: _StubQP())
    app = create_app()
    client = TestClient(app)
    resp = client.post("/query", json={"question": "How many tickets?"})
    body = resp.json()
    assert body["status"] == "dependency_error"
    assert body["evidence"] is None


def test_ungrounded_answer_refused(monkeypatch):
    plan = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "filters": [{"field": "priority", "op": "eq", "value": "P1"}],
    })
    import dspy
    from app.api import routes

    class _StubQP:
        def __call__(self, question):
            req = StructuredQueryRequest.model_validate(json.loads(plan))
            return dspy.Prediction(classification="supported",
                                   rationale="stub", request=req)

    class _StubAP:
        def __call__(self, question, evidence):
            # Fabricated number not in evidence.
            return dspy.Prediction(answer="There are 999999 tickets.",
                                   grounded=False)

    monkeypatch.setattr(routes, "_make_query_program", lambda: _StubQP())
    monkeypatch.setattr(routes, "_make_answer_program", lambda: _StubAP())
    app = create_app()
    client = TestClient(app)
    resp = client.post("/query", json={"question": "How many P1 tickets?"})
    body = resp.json()
    # Ungrounded answer must not be presented as fact.
    assert body["status"] in ("clarification", "unsupported", "answered")
    if body["status"] == "answered":
        assert "999999" not in body["answer"]


def test_health_endpoint(monkeypatch):
    app = create_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
