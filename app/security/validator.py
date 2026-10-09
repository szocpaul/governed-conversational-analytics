"""Deterministic structured-request validation (T004).

Re-checks every governed constraint on a StructuredQueryRequest before any
GraphJin execution. This is a pure function with no LLM and no I/O: the same
input always produces the same decision.

Type discipline (F6/F9/F10): filter values must be non-null and compatible
with the column type, and avg/sum aggregates require a numeric field. These
checks reject requests that would otherwise fail inside GraphJin with a
database type error, turning them into the stable "unsupported" category
with zero governed calls.
"""
from __future__ import annotations

from app.api.schemas import (
    _NUMERIC_AGGREGATES,
    _ORDERABLE_TYPES,
    COLUMN_TYPES,
    ENTITIES,
    MAX_LIMIT,
    RELATIONSHIPS,
    StructuredQueryRequest,
)
from app.security.errors import ValidationError

_VALID_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "like"}
_VALID_AGG = {"count", "sum", "avg", "min", "max"}


def _value_matches_type(value: object, col_type: str) -> bool:
    """Return True when a filter literal is compatible with the column type.

    bool is checked before int because bool is a subclass of int in Python.
    Timestamps accept ISO date/datetime strings only.
    """
    if isinstance(value, bool):
        return col_type == "boolean"
    if col_type == "boolean":
        return False
    if isinstance(value, int):
        return col_type in ("integer", "numeric")
    if isinstance(value, float):
        return col_type == "numeric"
    if isinstance(value, str):
        if col_type == "text":
            return True
        if col_type == "timestamp":
            # Accept ISO 8601 date or datetime strings.
            from datetime import date, datetime
            for parser in (datetime.fromisoformat, date.fromisoformat):
                try:
                    parser(value)
                    return True
                except ValueError:
                    continue
            return False
        # integer/numeric columns must not receive string literals (F9).
        return False
    return False


def _check_filter_value(field: str, op: str, value: object) -> None:
    """Validate a single filter value against the column type."""
    col_type = COLUMN_TYPES.get(field)
    if col_type is None:
        # Unknown column: the allowlist check reports it separately.
        return
    if value is None:
        # No is-null operator exists in the governed schema (F10).
        raise ValidationError(
            f"null filter value on {field!r} is unsupported; "
            "no is-null operator is available")
    if op == "in":
        if not isinstance(value, (list, tuple)) or not value:
            raise ValidationError(
                f"in operator on {field!r} requires a non-empty list")
        for item in value:
            if item is None or not _value_matches_type(item, col_type):
                raise ValidationError(
                    f"filter value {item!r} is not compatible with the "
                    f"type of field {field!r}")
        return
    if not _value_matches_type(value, col_type):
        raise ValidationError(
            f"filter value {value!r} is not compatible with the type of "
            f"field {field!r}")


def validate_request(req: StructuredQueryRequest) -> StructuredQueryRequest:
    """Validate a structured request against the governed policy.

    Returns the request unchanged when valid; raises ValidationError with a
    stable code otherwise. Deterministic: no model, no randomness, no I/O.
    """
    if req.entity not in ENTITIES:
        raise ValidationError(f"unsupported entity: {req.entity!r}")
    allowed = ENTITIES[req.entity]

    if req.operation not in ("list", "aggregate"):
        raise ValidationError(f"unsupported operation: {req.operation!r}")

    for f in req.fields:
        if f not in allowed:
            raise ValidationError(
                f"field {f!r} not allowed on entity {req.entity!r}")

    for flt in req.filters:
        if flt.field not in allowed:
            raise ValidationError(
                f"filter field {flt.field!r} not allowed on {req.entity!r}")
        if flt.op not in _VALID_OPS:
            raise ValidationError(f"invalid filter operator: {flt.op!r}")
        _check_filter_value(flt.field, flt.op, flt.value)

    for rel in req.relationships:
        if rel not in RELATIONSHIPS[req.entity]:
            raise ValidationError(
                f"relationship {rel!r} not allowed on {req.entity!r}")

    if not (1 <= req.limit <= MAX_LIMIT):
        raise ValidationError(
            f"limit {req.limit} out of range 1..{MAX_LIMIT}")

    if req.order_by is not None and req.order_by not in allowed:
        raise ValidationError(
            f"order_by field {req.order_by!r} not allowed on {req.entity!r}")

    if req.operation == "aggregate":
        if req.aggregate is None:
            raise ValidationError("aggregate operation requires aggregate")
        if req.aggregate.function not in _VALID_AGG:
            raise ValidationError(
                f"invalid aggregate function: {req.aggregate.function!r}")
        if req.aggregate.function != "count":
            if not req.aggregate.field:
                raise ValidationError(
                    f"aggregate {req.aggregate.function} requires a field")
            if req.aggregate.field not in allowed:
                raise ValidationError(
                    f"aggregate field {req.aggregate.field!r} not allowed on "
                    f"{req.entity!r}")
            field_type = COLUMN_TYPES.get(req.aggregate.field)
            if req.aggregate.function in _NUMERIC_AGGREGATES and \
                    field_type != "numeric":
                # avg/sum on boolean/text/timestamp fails in the database
                # (e.g. avg(boolean) does not exist) — reject early (F6).
                raise ValidationError(
                    f"aggregate {req.aggregate.function} requires a numeric "
                    f"field; {req.aggregate.field!r} is {field_type}")
            if req.aggregate.function in ("min", "max") and \
                    field_type not in _ORDERABLE_TYPES and \
                    field_type != "text":
                raise ValidationError(
                    f"aggregate {req.aggregate.function} does not support "
                    f"field {req.aggregate.field!r} of type {field_type}")

    return req
