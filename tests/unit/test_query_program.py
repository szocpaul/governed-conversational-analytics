"""Unit tests for the DSPy query program (T003).

Covers supported, relationship, time-filter, and empty-result planning.
LLM calls are stubbed so tests are fast and deterministic; the parsing and
validation logic under test is real.
"""
from __future__ import annotations

import json

import pytest

from app.api.schemas import StructuredQueryRequest
from app.ai.query_program import QueryProgram, parse_request_json


# ---------------------------------------------------------------------------
# parse_request_json (deterministic, no LLM)
# ---------------------------------------------------------------------------

def test_parse_valid_list_request():
    raw = json.dumps({
        "entity": "tickets", "operation": "list",
        "fields": ["ticket_id", "priority"],
        "filters": [{"field": "priority", "op": "eq", "value": "P1"}],
        "limit": 5,
    })
    req = parse_request_json(raw)
    assert isinstance(req, StructuredQueryRequest)
    assert req.entity == "tickets"
    assert req.limit == 5


def test_parse_strips_code_fences():
    nl = chr(10)
    raw = "```json" + nl + json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
    }) + nl + "```"
    req = parse_request_json(raw)
    assert req.operation == "aggregate"


def test_parse_rejects_non_json():
    with pytest.raises(ValueError):
        parse_request_json("SELECT * FROM tickets;")


def test_parse_rejects_sql_in_json():
    raw = json.dumps({"entity": "tickets; DROP TABLE tickets;",
                      "operation": "list", "fields": ["ticket_id"]})
    with pytest.raises(ValueError):
        parse_request_json(raw)


def test_parse_relationship_request():
    raw = json.dumps({
        "entity": "tickets", "operation": "list",
        "fields": ["ticket_id"],
        "relationships": ["merchants"],
        "limit": 3,
    })
    req = parse_request_json(raw)
    assert req.relationships == ["merchants"]


def test_parse_time_filter_request():
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "filters": [{"field": "created_at", "op": "gte", "value": "2026-01-01"},
                    {"field": "created_at", "op": "lt", "value": "2026-02-01"}],
    })
    req = parse_request_json(raw)
    assert len(req.filters) == 2


# ---------------------------------------------------------------------------
# QueryProgram.forward with stubbed predictors
# ---------------------------------------------------------------------------

class _Stub:
    def __init__(self, **kw):
        self._kw = kw

    def __call__(self, **kwargs):
        import dspy
        return dspy.Prediction(**self._kw)


def _program(monkeypatch, classify_out, plan_out):
    prog = QueryProgram()
    monkeypatch.setattr(prog, "classify", _Stub(**classify_out))
    monkeypatch.setattr(prog, "plan", _Stub(**plan_out))
    return prog


def test_supported_question_produces_request(monkeypatch):
    plan = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "filters": [{"field": "priority", "op": "eq", "value": "P1"}],
    })
    prog = _program(
        monkeypatch,
        {"category": "supported", "rationale": "count of P1 tickets"},
        {"request_json": plan},
    )
    out = prog(question="How many P1 tickets are there?")
    assert out.classification == "supported"
    assert isinstance(out.request, StructuredQueryRequest)
    assert out.request.aggregate.function == "count"


def test_ambiguous_question_no_request(monkeypatch):
    prog = _program(
        monkeypatch,
        {"category": "ambiguous", "rationale": "unclear time range"},
        {"request_json": ""},
    )
    out = prog(question="Show me recent stuff")
    assert out.classification == "ambiguous"
    assert out.request is None


def test_unsupported_question_no_request(monkeypatch):
    prog = _program(
        monkeypatch,
        {"category": "unsupported", "rationale": "not an ITSM question"},
        {"request_json": ""},
    )
    out = prog(question="What is the weather today?")
    assert out.classification == "unsupported"
    assert out.request is None


def test_malformed_plan_raises(monkeypatch):
    prog = _program(
        monkeypatch,
        {"category": "supported", "rationale": "x"},
        {"request_json": "not json at all"},
    )
    with pytest.raises(ValueError):
        prog(question="How many tickets?")


# ---------------------------------------------------------------------------
# v2 shape normalization (spec 005, T004)
# ---------------------------------------------------------------------------

from app.ai.query_program import UnsupportedShapeError


def test_group_by_key_accepted_and_normalized():
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "group_by": ["category"], "order_by": "count", "order_dir": "desc",
    })
    req = parse_request_json(raw)
    assert req.group_by == ["category"]
    assert req.order_by == "count"


def test_having_key_accepted_and_normalized():
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "group_by": ["merchant_id"],
        "having": {"function": "count", "field": None, "op": "gt",
                   "value": 50},
    })
    req = parse_request_json(raw)
    assert req.having is not None
    assert req.having.value == 50


def test_is_null_filter_accepted():
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "count", "field": None},
        "filters": [{"field": "assigned_agent_id", "op": "is_null",
                     "value": None}],
    })
    req = parse_request_json(raw)
    assert req.filters[0].op == "is_null"


def test_ratio_aggregate_accepted():
    raw = json.dumps({
        "entity": "tickets", "operation": "aggregate",
        "aggregate": {"function": "ratio", "field": "resolution_breached"},
    })
    req = parse_request_json(raw)
    assert req.aggregate.function == "ratio"


def test_joins_still_rejected():
    raw = json.dumps({
        "entity": "tickets", "operation": "list", "fields": ["ticket_id"],
        "joins": ["merchants"],
    })
    with pytest.raises(UnsupportedShapeError):
        parse_request_json(raw)


def test_subquery_still_rejected():
    raw = json.dumps({
        "entity": "tickets", "operation": "list", "fields": ["ticket_id"],
        "subquery": {"entity": "agents"},
    })
    with pytest.raises(UnsupportedShapeError):
        parse_request_json(raw)


def test_union_still_rejected():
    raw = json.dumps({
        "entity": "tickets", "operation": "list", "fields": ["ticket_id"],
        "union": [{"entity": "agents"}],
    })
    with pytest.raises(UnsupportedShapeError):
        parse_request_json(raw)


def test_distinct_as_key_still_rejected():
    # distinct as a top-level planner key is not the governed grouped shape;
    # grouping must go through group_by.
    raw = json.dumps({
        "entity": "tickets", "operation": "list", "fields": ["category"],
        "distinct": True,
    })
    with pytest.raises(UnsupportedShapeError):
        parse_request_json(raw)


def test_group_alias_keys_still_rejected():
    # "group"/"groupby" aliases are not the canonical group_by shape.
    for alias in ("group", "groupby"):
        raw = json.dumps({
            "entity": "tickets", "operation": "aggregate",
            "aggregate": {"function": "count", "field": None},
            alias: ["category"],
        })
        with pytest.raises(UnsupportedShapeError):
            parse_request_json(raw)
