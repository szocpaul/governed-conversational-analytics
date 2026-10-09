"""Contract tests for the conversational query API and typed request models (T002).

These tests define the stable shapes exchanged between the API, the DSPy
planning stage, the deterministic validator, and the governed GraphJin
execution path. They are written before the implementation and must fail
until app/api/schemas.py and app/ai/signatures.py exist.
"""
from __future__ import annotations

import pytest

pydantic = pytest.importorskip("pydantic")
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Typed request / answer schemas
# ---------------------------------------------------------------------------

def test_structured_request_valid_list():
    from app.api.schemas import StructuredQueryRequest

    req = StructuredQueryRequest(
        entity="tickets",
        operation="list",
        fields=["ticket_id", "category", "priority"],
        filters=[{"field": "priority", "op": "eq", "value": "P1"}],
        limit=10,
    )
    assert req.entity == "tickets"
    assert req.operation == "list"
    assert req.limit == 10


def test_structured_request_valid_aggregate():
    from app.api.schemas import StructuredQueryRequest

    req = StructuredQueryRequest(
        entity="tickets",
        operation="aggregate",
        aggregate={"function": "avg", "field": "resolution_hours"},
        filters=[{"field": "priority", "op": "eq", "value": "P1"}],
    )
    assert req.aggregate.function == "avg"
    assert req.aggregate.field == "resolution_hours"


def test_structured_request_rejects_unknown_entity():
    from app.api.schemas import StructuredQueryRequest

    with pytest.raises(ValidationError):
        StructuredQueryRequest(entity="users", operation="list",
                               fields=["ticket_id"])


def test_structured_request_rejects_unknown_field():
    from app.api.schemas import StructuredQueryRequest

    with pytest.raises(ValidationError):
        StructuredQueryRequest(entity="tickets", operation="list",
                               fields=["password"])


def test_structured_request_rejects_write_operation():
    from app.api.schemas import StructuredQueryRequest

    with pytest.raises(ValidationError):
        StructuredQueryRequest(entity="tickets", operation="delete")


def test_structured_request_time_filter():
    from app.api.schemas import StructuredQueryRequest

    req = StructuredQueryRequest(
        entity="tickets",
        operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "created_at", "op": "gte", "value": "2026-01-01"}],
    )
    assert req.filters[0].op == "gte"


def test_structured_request_limit_capped():
    from app.api.schemas import StructuredQueryRequest

    with pytest.raises(ValidationError):
        StructuredQueryRequest(entity="tickets", operation="list",
                               fields=["ticket_id"], limit=100000)


def test_answer_requires_evidence_reference():
    from app.api.schemas import QueryAnswer

    ans = QueryAnswer(
        status="answered",
        answer="There are 112 P1 tickets.",
        evidence={"rows": [], "aggregate": {"count": 112}},
    )
    assert ans.status == "answered"
    assert ans.evidence is not None


def test_refusal_categories_stable():
    from app.api.schemas import QueryAnswer

    for status in ("clarification", "unsupported", "dependency_error"):
        ans = QueryAnswer(status=status, answer="...", evidence=None)
        assert ans.status == status


def test_trace_and_latency_present():
    from app.api.schemas import QueryResponse

    resp = QueryResponse(
        status="answered",
        answer="ok",
        evidence={"rows": [], "aggregate": None},
        trace=[{"event": "classified"}, {"event": "executed"}],
        latency_ms=12.5,
    )
    assert resp.latency_ms == 12.5
    assert isinstance(resp.trace, list)
    assert resp.trace[0].event == "classified"


# ---------------------------------------------------------------------------
# DSPy signatures
# ---------------------------------------------------------------------------

def test_dspy_signatures_exist_and_typed():
    from app.ai import signatures

    assert hasattr(signatures, "ClassifyQuestion")
    assert hasattr(signatures, "PlanQuery")
    assert hasattr(signatures, "GroundAnswer")
    # Signatures are dspy.Signature subclasses with typed fields.
    import dspy

    for sig in (signatures.ClassifyQuestion, signatures.PlanQuery,
                signatures.GroundAnswer):
        assert issubclass(sig, dspy.Signature)
        assert sig.input_fields, sig
        assert sig.output_fields, sig
