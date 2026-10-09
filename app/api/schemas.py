"""Typed API and structured-request models for the conversational pipeline.

These models are the contract between the FastAPI surface, the DSPy planning
stage, the deterministic validator, and the governed GraphJin execution path.
They enforce the governed entity/field allowlist at the type level so that an
invalid structured request fails fast, before any database access.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Governed allowlist (mirrors graphjin/config/policies.yml). The validator
# re-checks these deterministically; keeping them here fails fast at the
# type boundary.
ENTITIES: dict[str, set[str]] = {
    "merchants": {"merchant_id", "merchant_name", "sector", "tier", "region"},
    "agents": {
        "agent_id", "agent_name", "tier", "primary_category",
        "shift_region", "efficiency_multiplier",
    },
    "tickets": {
        "ticket_id", "merchant_id", "category", "sub_category", "priority",
        "created_at", "is_legacy", "assigned_agent_id", "category_mismatch",
        "first_response_at", "closed_at", "ttfr_hours", "resolution_hours",
        "response_breached", "resolution_breached", "is_reopened",
        "is_reopen_child", "is_incident_ticket", "csat_score",
    },
}

# GraphJin relationship field names (plural) reachable from each entity.
RELATIONSHIPS: dict[str, set[str]] = {
    "tickets": {"merchants", "agents"},
    "merchants": {"tickets"},
    "agents": {"tickets"},
}

MAX_LIMIT = 100  # matches GraphJin default_limit hard cap

FilterOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "like"]
AggregateFunction = Literal["count", "sum", "avg", "min", "max"]
Operation = Literal["list", "aggregate"]
AnswerStatus = Literal["answered", "clarification", "unsupported",
                       "dependency_error"]


class Filter(BaseModel):
    field: str
    op: FilterOp
    value: object = None


class Aggregate(BaseModel):
    function: AggregateFunction
    field: Optional[str] = None  # None allowed only for count


class StructuredQueryRequest(BaseModel):
    """A typed, governed query request produced by the planning stage."""

    entity: str
    operation: Operation
    fields: list[str] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    aggregate: Optional[Aggregate] = None
    relationships: list[str] = Field(default_factory=list)
    order_by: Optional[str] = None
    order_dir: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=MAX_LIMIT, ge=1, le=MAX_LIMIT)

    @field_validator("entity")
    @classmethod
    def _entity_allowed(cls, v: str) -> str:
        if v not in ENTITIES:
            raise ValueError(f"unsupported entity: {v!r}")
        return v

    @model_validator(mode="after")
    def _check_shape(self) -> "StructuredQueryRequest":
        allowed = ENTITIES[self.entity]
        for f in self.fields:
            if f not in allowed:
                raise ValueError(
                    f"field {f!r} not allowed on entity {self.entity!r}")
        for flt in self.filters:
            if flt.field not in allowed:
                raise ValueError(
                    f"filter field {flt.field!r} not allowed on "
                    f"{self.entity!r}")
        for rel in self.relationships:
            if rel not in RELATIONSHIPS[self.entity]:
                raise ValueError(
                    f"relationship {rel!r} not allowed on {self.entity!r}")
        if self.operation == "aggregate":
            if self.aggregate is None:
                raise ValueError("aggregate operation requires aggregate")
            if self.aggregate.function != "count":
                if not self.aggregate.field:
                    raise ValueError(
                        f"aggregate {self.aggregate.function} requires a field")
                if self.aggregate.field not in allowed:
                    raise ValueError(
                        f"aggregate field {self.aggregate.field!r} not "
                        f"allowed on {self.entity!r}")
        if self.order_by and self.order_by not in allowed:
            raise ValueError(
                f"order_by field {self.order_by!r} not allowed on "
                f"{self.entity!r}")
        return self


class Evidence(BaseModel):
    """Normalized execution evidence. Answers must be grounded in this."""

    rows: list[dict] = Field(default_factory=list)
    aggregate: Optional[dict] = None
    row_count: int = 0


class TraceEvent(BaseModel):
    event: str
    detail: Optional[str] = None


class QueryAnswer(BaseModel):
    status: AnswerStatus
    answer: str
    evidence: Optional[Evidence] = None


class QueryResponse(BaseModel):
    status: AnswerStatus
    answer: str
    evidence: Optional[Evidence] = None
    trace: list[TraceEvent] = Field(default_factory=list)
    latency_ms: float = 0.0


class QuestionRequest(BaseModel):
    """Inbound user question."""

    question: str = Field(min_length=1)
