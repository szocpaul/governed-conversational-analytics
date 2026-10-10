"""Regression tests for the T010-review correctness findings (F1-F4, F6-F10).

Each finding was verified against the live database during human review.
The fixes are deterministic: unsupported shapes are rejected BEFORE GraphJin
(zero governed calls), schema mismatches are normalized or rejected with a
stable category, and the grounding check no longer refuses answers that
legitimately echo question filter terms.

Ground truths (verified against the DB):
- F2: P1=49, P2=163 tickets after 2026-01-01 (GROUP BY -> unsupported)
- F3: highest efficiency_multiplier = Samira Khan 1.355
- F4: avg resolution_hours for P1 + Account Access = 2.34
- F5 (control): reopened count = 307
- F8: top category = Payments & Checkout (483) (GROUP BY -> unsupported)
- F9: 'Acme Corp' does not exist in merchants
- F10: 250 tickets with assigned_agent_id IS NULL
"""
from __future__ import annotations

import json

import pytest

from app.ai.query_program import parse_request_json
from app.api.schemas import Aggregate, Filter, StructuredQueryRequest
from app.security.errors import ValidationError as GovernedValidationError
from app.security.validator import validate_request


# ---------------------------------------------------------------------------
# Class A: unsupported shapes must be rejected before GraphJin
# ---------------------------------------------------------------------------

def test_f2_group_by_parsed_not_silently_dropped():
    """F2/F8 (updated by spec 005): group_by is now a SUPPORTED governed
    shape. It must be parsed into the typed request — never silently
    rewritten to a plain count, and never rejected as unsupported."""
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "filters": [
            {"field": "priority", "op": "in", "value": ["P1", "P2"]},
            {"field": "created_at", "op": "gte", "value": "2026-01-01"},
        ],
        "group_by": ["category"],
        "limit": 100,
    })
    req = parse_request_json(raw)
    assert req.group_by == ["category"]
    assert len(req.filters) == 2


def test_f8_group_by_simple_accepted():
    # Spec 005 FR-001: grouped aggregation is a governed shape.
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "group_by": ["category"],
        "limit": 100,
    })
    req = parse_request_json(raw)
    assert req.group_by == ["category"]


def test_group_alias_keys_still_rejected():
    # The non-canonical aliases remain unsupported shapes.
    for alias in ("group", "groupby"):
        raw = json.dumps({
            "entity": "tickets", "operation": "aggregate",
            "aggregate": {"function": "count", "field": None},
            alias: ["category"],
            "limit": 100,
        })
        with pytest.raises(ValueError, match="(?i)unsupported|group"):
            parse_request_json(raw)


def test_having_rejected():
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "having": {"count": {"gt": 50}},
        "limit": 100,
    })
    with pytest.raises(ValueError):
        parse_request_json(raw)


def test_f6_avg_on_boolean_rejected():
    """F6: avg(resolution_breached) on a boolean field must be rejected by
    the deterministic validator before any GraphJin call."""
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="aggregate", fields=[], filters=[],
        aggregate=Aggregate(function="avg", field="resolution_breached"),
        relationships=[], order_by=None, order_dir="asc", limit=100)
    with pytest.raises(GovernedValidationError, match="(?i)numeric|boolean|type"):
        validate_request(req)


def test_sum_on_boolean_rejected():
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="aggregate", fields=[], filters=[],
        aggregate=Aggregate(function="sum", field="is_legacy"),
        relationships=[], order_by=None, order_dir="asc", limit=100)
    with pytest.raises(GovernedValidationError):
        validate_request(req)


def test_avg_on_numeric_allowed():
    req = StructuredQueryRequest(
        entity="tickets", operation="aggregate",
        aggregate={"function": "avg", "field": "resolution_hours"})
    assert validate_request(req) is req


def test_count_on_any_field_allowed():
    req = StructuredQueryRequest(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "resolution_breached", "op": "eq", "value": True}])
    assert validate_request(req) is req


def test_f9_string_value_on_integer_field_rejected():
    """F9: filter merchant_id (integer) with a string value must be rejected
    by the validator before GraphJin (invalid integer syntax upstream)."""
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="aggregate", fields=[],
        filters=[Filter(field="merchant_id", op="eq", value="Acme Corp")],
        aggregate=Aggregate(function="count", field=None),
        relationships=[], order_by=None, order_dir="asc", limit=100)
    with pytest.raises(GovernedValidationError, match="(?i)type|integer|value|compatible"):
        validate_request(req)


def test_integer_value_on_integer_field_allowed():
    req = StructuredQueryRequest(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "merchant_id", "op": "eq", "value": 101}])
    assert validate_request(req) is req


def test_f10_null_filter_value_rejected():
    """F10: there is no is-null operator; a null filter value must be
    rejected as unsupported before GraphJin (not sent as "None")."""
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="list", fields=["ticket_id"],
        filters=[Filter(field="assigned_agent_id", op="eq", value=None)],
        aggregate=None, relationships=[], order_by=None, order_dir="asc",
        limit=100)
    with pytest.raises(GovernedValidationError, match="(?i)null|none|value"):
        validate_request(req)


def test_string_none_on_integer_field_rejected():
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="list", fields=["ticket_id"],
        filters=[Filter(field="assigned_agent_id", op="eq", value="None")],
        aggregate=None, relationships=[], order_by=None, order_dir="asc",
        limit=100)
    with pytest.raises(GovernedValidationError):
        validate_request(req)


# ---------------------------------------------------------------------------
# Class B: schema mismatch normalization (F7)
# ---------------------------------------------------------------------------

def test_f7_order_by_list_normalized():
    """F7: planner emitted order_by as [{field, direction}]; normalize to
    order_by str + order_dir instead of surfacing a pydantic error."""
    raw = json.dumps({
        "entity": "tickets", "operation": "list",
        "fields": ["ticket_id", "created_at"],
        "order_by": [{"field": "created_at", "direction": "asc"}],
        "limit": 5,
    })
    req = parse_request_json(raw)
    assert req.order_by == "created_at"
    assert req.order_dir == "asc"


def test_f7_order_by_list_desc_normalized():
    raw = json.dumps({
        "entity": "agents", "operation": "list",
        "fields": ["agent_name", "efficiency_multiplier"],
        "order_by": [{"field": "efficiency_multiplier", "direction": "desc"}],
        "limit": 1,
    })
    req = parse_request_json(raw)
    assert req.order_by == "efficiency_multiplier"
    assert req.order_dir == "desc"


def test_order_by_multi_field_list_rejected():
    """Multi-field ordering is not supported; reject with a stable error."""
    raw = json.dumps({
        "entity": "tickets", "operation": "list",
        "fields": ["ticket_id"],
        "order_by": [{"field": "created_at", "direction": "asc"},
                     {"field": "priority", "direction": "desc"}],
        "limit": 5,
    })
    with pytest.raises(ValueError):
        parse_request_json(raw)


# ---------------------------------------------------------------------------
# Class C: grounding (F3, F4)
# ---------------------------------------------------------------------------

def test_f4_question_filter_terms_grounded():
    """F4: an answer that echoes the question's filter terms (e.g. the
    category name) is grounded when the numeric value matches evidence."""
    from app.ai.answer_program import is_grounded
    from app.api.schemas import Evidence
    ev = Evidence(rows=[], aggregate={"avg_resolution_hours": 2.340125110692032},
                  row_count=0)
    answer = ("The average resolution time for P1 tickets in the "
              "Account Access category is approximately 2.34 hours.")
    assert is_grounded(answer, ev, question=(
        "avg resolution time for P1 tickets in Account Access category?"))


def test_ungrounded_name_still_detected_with_question():
    """A proper noun absent from BOTH evidence and question is ungrounded."""
    from app.ai.answer_program import is_grounded
    from app.api.schemas import Evidence
    ev = Evidence(rows=[{"agent_name": "Samira Khan",
                         "efficiency_multiplier": 1.355}], row_count=1)
    answer = "Alex Mercer has the highest efficiency multiplier (1.355)."
    assert is_grounded(answer, ev, question=(
        "Which agent has the highest efficiency multiplier?")) is False


def test_f3_correct_answer_grounded():
    """F3 ground truth: Samira Khan 1.355 in evidence -> answer grounded."""
    from app.ai.answer_program import is_grounded
    from app.api.schemas import Evidence
    ev = Evidence(rows=[{"agent_id": 215, "agent_name": "Samira Khan",
                         "efficiency_multiplier": 1.355}], row_count=1)
    answer = "Samira Khan has the highest efficiency multiplier (1.355)."
    assert is_grounded(answer, ev, question=(
        "Which agent has the highest efficiency multiplier?")) is True


def test_no_data_claim_with_nonempty_evidence_ungrounded():
    """F6 follow-up: claiming 'no matching data' when evidence contains a
    real aggregate value (count=1037) contradicts the evidence -> ungrounded."""
    from app.ai.answer_program import is_grounded
    from app.api.schemas import Evidence
    ev = Evidence(rows=[], aggregate={"count": 1037}, row_count=0)
    assert is_grounded("No matching data was found.", ev) is False


def test_no_data_claim_with_null_aggregate_grounded():
    """A no-data claim is grounded when every aggregate value is null."""
    from app.ai.answer_program import is_grounded
    from app.api.schemas import Evidence
    ev = Evidence(rows=[], aggregate={"avg_resolution_hours": None}, row_count=0)
    assert is_grounded("No matching data was found.", ev) is True
