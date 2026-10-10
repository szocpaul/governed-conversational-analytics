"""Validator tests for the extended request surface v2 (spec 005, T002).

Covers every new allowlist rule and rejection from
contracts/structured-query-request-v2.md: group_by on non-allowlisted field,
having without group_by, having with string threshold, ratio on non-boolean
field, is_null with non-null value, group_by on list operation. The validator
re-checks deterministically before any GraphJin call, even when the pydantic
type boundary was bypassed via model_construct.
"""
from __future__ import annotations

import pytest

from app.api.schemas import (
    Aggregate,
    Filter,
    HavingFilter,
    StructuredQueryRequest,
)
from app.security.errors import ValidationError as GovernedValidationError
from app.security.validator import validate_request


def _construct(**over):
    """Bypass the pydantic type boundary (validator must still catch it)."""
    base = dict(
        entity="tickets", operation="aggregate", fields=[], filters=[],
        aggregate=Aggregate(function="count", field=None),
        relationships=[], group_by=["category"], having=None,
        order_by=None, order_dir="asc", limit=100)
    base.update(over)
    return StructuredQueryRequest.model_construct(**base)


# ---------------------------------------------------------------------------
# Accepted new shapes
# ---------------------------------------------------------------------------

def test_grouped_count_accepted():
    req = validate_request(_construct())
    assert req.group_by == ["category"]


def test_having_accepted():
    req = validate_request(_construct(
        group_by=["merchant_id"],
        having=HavingFilter(function="count", field=None, op="gt",
                            value=50)))
    assert req.having.op == "gt"


def test_is_null_filter_accepted():
    req = validate_request(_construct(
        group_by=[],
        filters=[Filter(field="assigned_agent_id", op="is_null",
                        value=None)]))
    assert req.filters[0].op == "is_null"


def test_is_not_null_filter_accepted():
    req = validate_request(_construct(
        group_by=[],
        filters=[Filter(field="closed_at", op="is_not_null", value=None)]))
    assert req.filters[0].op == "is_not_null"


def test_ratio_aggregate_accepted():
    req = validate_request(_construct(
        group_by=[],
        aggregate=Aggregate(function="ratio", field="resolution_breached")))
    assert req.aggregate.function == "ratio"


def test_ratio_per_group_accepted():
    req = validate_request(_construct(
        group_by=["category"],
        aggregate=Aggregate(function="ratio", field="resolution_breached")))
    assert req.group_by == ["category"]


def test_grouped_order_by_count_accepted():
    req = validate_request(_construct(order_by="count", order_dir="desc"))
    assert req.order_by == "count"


def test_grouped_order_by_aggregate_column_accepted():
    req = validate_request(_construct(order_by="count_ticket_id",
                                      order_dir="desc"))
    assert req.order_by == "count_ticket_id"


# ---------------------------------------------------------------------------
# Rejections: group_by
# ---------------------------------------------------------------------------

def test_group_by_non_allowlisted_field_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=["salary"]))


def test_group_by_on_list_operation_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(operation="list",
                                    fields=["ticket_id"], aggregate=None))


def test_group_by_too_many_fields_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=["category", "priority", "is_legacy", "sub_category"]))


def test_group_by_without_aggregate_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(aggregate=None))


def test_group_by_relationship_traversal_rejected():
    # Relationship traversal attempts must not validate as group fields.
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=["merchants.sector"]))
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=["agents"]))


# ---------------------------------------------------------------------------
# Rejections: having
# ---------------------------------------------------------------------------

def test_having_without_group_by_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[],
            having=HavingFilter(function="count", field=None, op="gt",
                                value=50)))


def test_having_string_threshold_rejected():
    having = HavingFilter.model_construct(function="count", field=None,
                                          op="gt", value="50; DROP TABLE")
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_bool_threshold_rejected():
    having = HavingFilter.model_construct(function="count", field=None,
                                          op="gt", value=True)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_invalid_function_rejected():
    having = HavingFilter.model_construct(function="median", field=None,
                                          op="gt", value=5)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_invalid_op_rejected():
    having = HavingFilter.model_construct(function="count", field=None,
                                          op="like", value=5)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_non_count_requires_field():
    having = HavingFilter.model_construct(function="sum", field=None,
                                          op="gt", value=5)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_sum_on_text_field_rejected():
    having = HavingFilter.model_construct(function="sum", field="category",
                                          op="gt", value=5)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_field_not_allowlisted_rejected():
    having = HavingFilter.model_construct(function="avg", field="salary",
                                          op="gt", value=5)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


# ---------------------------------------------------------------------------
# Rejections: is_null / is_not_null
# ---------------------------------------------------------------------------

def test_is_null_with_non_null_value_rejected():
    flt = Filter.model_construct(field="closed_at", op="is_null",
                                 value="2026-01-01")
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=[], filters=[flt]))


def test_is_not_null_with_value_rejected():
    flt = Filter.model_construct(field="closed_at", op="is_not_null",
                                 value=0)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=[], filters=[flt]))


def test_is_null_on_non_allowlisted_field_rejected():
    flt = Filter.model_construct(field="password_hash", op="is_null",
                                 value=None)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=[], filters=[flt]))


# ---------------------------------------------------------------------------
# Rejections: ratio
# ---------------------------------------------------------------------------

def test_ratio_on_non_boolean_field_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[],
            aggregate=Aggregate(function="ratio", field="category")))


def test_ratio_on_numeric_field_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[],
            aggregate=Aggregate(function="ratio", field="csat_score")))


def test_ratio_without_field_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[], aggregate=Aggregate(function="ratio", field=None)))


def test_ratio_on_non_allowlisted_field_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[],
            aggregate=Aggregate(function="ratio", field="secret_flag")))


# ---------------------------------------------------------------------------
# Rejections: order_by on grouped requests
# ---------------------------------------------------------------------------

def test_grouped_order_by_non_allowlisted_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(order_by="salary"))


def test_grouped_order_by_unrelated_aggregate_name_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(order_by="avg_resolution_hours"))
