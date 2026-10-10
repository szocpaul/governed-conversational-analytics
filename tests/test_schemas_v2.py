"""Schema tests for the extended StructuredQueryRequest v2 (spec 005, T001).

Covers the new typed shapes: group_by (1-3 allowlisted fields, aggregate-only),
having (requires non-empty group_by; function in {count,sum,avg,min,max};
op in {eq,ne,gt,gte,lt,lte}; numeric value; non-count functions require an
allowlisted numeric field), is_null/is_not_null filter ops (value MUST be
null), and the ratio aggregate (field REQUIRED, allowlisted boolean column
only). Type-level enforcement fails fast before the deterministic validator.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.schemas import StructuredQueryRequest


def _grouped_count(**over):
    base = dict(
        entity="tickets",
        operation="aggregate",
        aggregate={"function": "count", "field": None},
        group_by=["category"],
    )
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# group_by
# ---------------------------------------------------------------------------

def test_group_by_single_field_accepted():
    req = StructuredQueryRequest.model_validate(_grouped_count())
    assert req.group_by == ["category"]


def test_group_by_multiple_fields_accepted():
    req = StructuredQueryRequest.model_validate(
        _grouped_count(group_by=["category", "priority"]))
    assert req.group_by == ["category", "priority"]


def test_group_by_three_fields_accepted():
    req = StructuredQueryRequest.model_validate(
        _grouped_count(group_by=["category", "priority", "is_legacy"]))
    assert len(req.group_by) == 3


def test_group_by_four_fields_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(
            _grouped_count(
                group_by=["category", "priority", "is_legacy",
                          "sub_category"]))


def test_group_by_non_allowlisted_field_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(
            _grouped_count(group_by=["salary"]))


def test_group_by_on_list_operation_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="list", fields=["ticket_id"],
            group_by=["category"]))


def test_group_by_default_empty():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="list", fields=["ticket_id"]))
    assert req.group_by == []


# ---------------------------------------------------------------------------
# having
# ---------------------------------------------------------------------------

def test_having_with_group_by_accepted():
    req = StructuredQueryRequest.model_validate(_grouped_count(
        group_by=["merchant_id"],
        having={"function": "count", "field": None, "op": "gt",
                "value": 50}))
    assert req.having is not None
    assert req.having.function == "count"
    assert req.having.op == "gt"
    assert req.having.value == 50


def test_having_without_group_by_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="aggregate",
            aggregate={"function": "count", "field": None},
            having={"function": "count", "field": None, "op": "gt",
                    "value": 50}))


def test_having_string_threshold_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(_grouped_count(
            having={"function": "count", "field": None, "op": "gt",
                    "value": "fifty"}))


def test_having_bool_threshold_rejected():
    # bool is an int subclass; thresholds must be genuine numbers.
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(_grouped_count(
            having={"function": "count", "field": None, "op": "gt",
                    "value": True}))


def test_having_invalid_function_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(_grouped_count(
            having={"function": "median", "field": None, "op": "gt",
                    "value": 5}))


def test_having_invalid_op_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(_grouped_count(
            having={"function": "count", "field": None, "op": "like",
                    "value": 5}))


def test_having_sum_requires_numeric_field():
    # sum on a text field must fail at the type boundary.
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(_grouped_count(
            having={"function": "sum", "field": "category", "op": "gt",
                    "value": 5}))


def test_having_sum_on_numeric_field_accepted():
    req = StructuredQueryRequest.model_validate(_grouped_count(
        having={"function": "avg", "field": "resolution_hours", "op": "gte",
                "value": 10.5}))
    assert req.having.function == "avg"
    assert req.having.field == "resolution_hours"


def test_having_non_count_requires_field():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(_grouped_count(
            having={"function": "sum", "field": None, "op": "gt",
                    "value": 5}))


def test_having_field_must_be_allowlisted():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(_grouped_count(
            having={"function": "avg", "field": "salary", "op": "gt",
                    "value": 5}))


# ---------------------------------------------------------------------------
# is_null / is_not_null filter ops
# ---------------------------------------------------------------------------

def test_is_null_filter_accepted():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "count", "field": None},
        filters=[{"field": "assigned_agent_id", "op": "is_null",
                  "value": None}]))
    assert req.filters[0].op == "is_null"


def test_is_not_null_filter_accepted():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="list", fields=["ticket_id"],
        filters=[{"field": "closed_at", "op": "is_not_null"}]))
    assert req.filters[0].op == "is_not_null"


def test_is_null_with_non_null_value_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="list", fields=["ticket_id"],
            filters=[{"field": "closed_at", "op": "is_null",
                      "value": "2026-01-01"}]))


def test_is_not_null_with_value_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="list", fields=["ticket_id"],
            filters=[{"field": "closed_at", "op": "is_not_null",
                      "value": 0}]))


# ---------------------------------------------------------------------------
# ratio aggregate
# ---------------------------------------------------------------------------

def test_ratio_on_boolean_field_accepted():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "ratio", "field": "resolution_breached"}))
    assert req.aggregate.function == "ratio"
    assert req.aggregate.field == "resolution_breached"


def test_ratio_requires_field():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="aggregate",
            aggregate={"function": "ratio", "field": None}))


def test_ratio_on_non_boolean_field_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="aggregate",
            aggregate={"function": "ratio", "field": "category"}))


def test_ratio_on_non_allowlisted_field_rejected():
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="aggregate",
            aggregate={"function": "ratio", "field": "secret_flag"}))


def test_ratio_per_group_accepted():
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "ratio", "field": "resolution_breached"},
        group_by=["category"]))
    assert req.group_by == ["category"]
    assert req.aggregate.function == "ratio"


def test_ratio_on_wrong_entity_field_rejected():
    # merchants has no boolean columns; ratio there must fail.
    with pytest.raises(PydanticValidationError):
        StructuredQueryRequest.model_validate(dict(
            entity="merchants", operation="aggregate",
            aggregate={"function": "ratio", "field": "tier"}))
