"""Deterministic structured-request validation (T004).

Re-checks every governed constraint on a StructuredQueryRequest before any
GraphJin execution. This is a pure function with no LLM and no I/O: the same
input always produces the same decision.
"""
from __future__ import annotations

from app.api.schemas import (
    ENTITIES,
    MAX_LIMIT,
    RELATIONSHIPS,
    StructuredQueryRequest,
)
from app.security.errors import ValidationError

_VALID_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "like"}
_VALID_AGG = {"count", "sum", "avg", "min", "max"}


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

    return req
