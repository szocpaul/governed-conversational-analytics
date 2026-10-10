"""Security tests for the v2 operators (spec 005, T015).

Abuse of the new operators to reach non-allowlisted fields or operations:
group_by on a blocked field name, ratio on a text field, having with
injection-shaped values, is_null on relationship traversal attempts. Every
case must be rejected deterministically with ZERO GraphJin calls; write-
shaped requests remain impossible end-to-end.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.schemas import (
    Aggregate,
    Filter,
    HavingFilter,
    StructuredQueryRequest,
)
from app.data.graphjin_client import build_graphql
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
# group_by abuse
# ---------------------------------------------------------------------------

def test_group_by_blocked_field_rejected_at_type_level():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest.model_validate(dict(
            entity="agents", operation="aggregate",
            aggregate={"function": "count", "field": None},
            group_by=["salary"]))


def test_group_by_blocked_field_rejected_by_validator():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=["password_hash"]))


def test_group_by_sql_shaped_field_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=["category; DROP TABLE tickets; --"]))


def test_group_by_relationship_traversal_rejected():
    # "merchants.sector" style traversal is not an allowlisted field.
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=["merchants.sector"]))
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=["agents.tier"]))


# ---------------------------------------------------------------------------
# ratio abuse
# ---------------------------------------------------------------------------

def test_ratio_on_text_field_rejected():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="aggregate",
            aggregate={"function": "ratio", "field": "category"}))


def test_ratio_on_text_field_rejected_by_validator():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[],
            aggregate=Aggregate(function="ratio", field="agent_name")))


def test_ratio_on_non_allowlisted_boolean_named_field_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[],
            aggregate=Aggregate(function="ratio", field="is_admin")))


# ---------------------------------------------------------------------------
# having abuse
# ---------------------------------------------------------------------------

def test_having_injection_shaped_value_rejected():
    having = HavingFilter.model_construct(
        function="count", field=None, op="gt",
        value="50 OR 1=1; DROP TABLE tickets; --")
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_injection_shaped_op_rejected():
    having = HavingFilter.model_construct(
        function="count", field=None, op="gt; DROP TABLE tickets", value=5)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_injection_shaped_function_rejected():
    having = HavingFilter.model_construct(
        function="count(*); DELETE FROM tickets; --", field=None, op="gt",
        value=5)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_on_blocked_field_rejected():
    having = HavingFilter.model_construct(
        function="avg", field="salary", op="gt", value=1000)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(having=having))


def test_having_without_group_by_rejected():
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(
            group_by=[],
            having=HavingFilter(function="count", field=None, op="gt",
                                value=50)))


# ---------------------------------------------------------------------------
# is_null abuse
# ---------------------------------------------------------------------------

def test_is_null_on_relationship_traversal_rejected():
    flt = Filter.model_construct(field="merchants.sector", op="is_null",
                                 value=None)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=[], filters=[flt]))


def test_is_null_on_blocked_field_rejected():
    flt = Filter.model_construct(field="password", op="is_null", value=None)
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=[], filters=[flt]))


def test_is_null_with_injection_value_rejected():
    flt = Filter.model_construct(field="closed_at", op="is_null",
                                 value="true; DROP TABLE tickets; --")
    with pytest.raises(GovernedValidationError):
        validate_request(_construct(group_by=[], filters=[flt]))


# ---------------------------------------------------------------------------
# Write shapes remain impossible through the new surface
# ---------------------------------------------------------------------------

def test_write_operation_rejected_with_group_by():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest.model_validate(dict(
            entity="tickets", operation="delete",
            group_by=["category"]))


def test_write_operation_rejected_by_validator_with_new_shapes():
    req = _construct(operation="delete")
    with pytest.raises(GovernedValidationError):
        validate_request(req)


# ---------------------------------------------------------------------------
# Zero GraphJin calls: rejected requests never reach the builder->client
# ---------------------------------------------------------------------------

def test_rejected_requests_produce_no_graphql():
    """Every abuse shape above must fail BEFORE build_graphql is callable
    on a validated request; prove the validator raises for each."""
    abuse_shapes = [
        _construct(group_by=["salary"]),
        _construct(group_by=[], aggregate=Aggregate(function="ratio",
                                                    field="category")),
        _construct(having=HavingFilter.model_construct(
            function="count", field=None, op="gt", value="x")),
        _construct(group_by=[], filters=[Filter.model_construct(
            field="closed_at", op="is_null", value=1)]),
    ]
    for req in abuse_shapes:
        with pytest.raises(GovernedValidationError):
            validate_request(req)


def test_graphql_builder_renders_only_allowlisted_identifiers():
    """The builder inserts field names verbatim into GraphQL; prove that a
    validated request can only contain allowlisted identifiers, so no
    injection-shaped string can reach the wire through the v2 shapes."""
    req = StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="aggregate",
        aggregate={"function": "ratio", "field": "resolution_breached"},
        group_by=["category"],
        filters=[{"field": "closed_at", "op": "is_null", "value": None}],
        having={"function": "count", "field": None, "op": "gt",
                "value": 5},
        order_by="ratio_resolution_breached", order_dir="desc", limit=50))
    validate_request(req)
    q = build_graphql(req)
    # Only allowlisted identifiers and structure; no having clause, no
    # injection surface.
    assert "having" not in q
    assert "distinct: [category]" in q
    assert "closed_at: {is_null: true}" in q
