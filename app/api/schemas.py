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

# Column value types (mirrors database/schema.sql). The deterministic
# validator uses these to reject type-incompatible filter values and
# aggregates BEFORE any GraphJin call (F6, F9, F10).
COLUMN_TYPES: dict[str, str] = {
    "merchant_id": "integer",
    "agent_id": "integer",
    "ticket_id": "integer",
    "assigned_agent_id": "integer",
    "merchant_name": "text",
    "sector": "text",
    "tier": "text",
    "region": "text",
    "agent_name": "text",
    "primary_category": "text",
    "shift_region": "text",
    "category": "text",
    "sub_category": "text",
    "priority": "text",
    "efficiency_multiplier": "numeric",
    "ttfr_hours": "numeric",
    "resolution_hours": "numeric",
    "csat_score": "numeric",
    "created_at": "timestamp",
    "first_response_at": "timestamp",
    "closed_at": "timestamp",
    "is_legacy": "boolean",
    "category_mismatch": "boolean",
    "response_breached": "boolean",
    "resolution_breached": "boolean",
    "is_reopened": "boolean",
    "is_reopen_child": "boolean",
    "is_incident_ticket": "boolean",
}

# Aggregate functions that require a numeric field (avg/sum). count works on
# any field; min/max work on numeric and timestamp fields.
_NUMERIC_AGGREGATES = {"avg", "sum"}
_ORDERABLE_TYPES = {"integer", "numeric", "timestamp"}

MAX_LIMIT = 100  # matches GraphJin default_limit hard cap

FilterOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "like",
                   "is_null", "is_not_null"]
AggregateFunction = Literal["count", "sum", "avg", "min", "max", "ratio"]
HavingFunction = Literal["count", "sum", "avg", "min", "max"]
HavingOp = Literal["eq", "ne", "gt", "gte", "lt", "lte"]
Operation = Literal["list", "aggregate"]
AnswerStatus = Literal["answered", "clarification", "unsupported",
                       "dependency_error"]

# Filter ops that carry no value (missing-value filtering, spec 005).
_NULL_OPS = {"is_null", "is_not_null"}

MAX_GROUP_BY = 3  # 1-3 grouping fields per grouped request


class Filter(BaseModel):
    field: str
    op: FilterOp
    value: object = None

    @model_validator(mode="after")
    def _null_ops_carry_no_value(self) -> "Filter":
        if self.op in _NULL_OPS and self.value is not None:
            raise ValueError(
                f"filter op {self.op!r} requires a null value")
        return self


class Aggregate(BaseModel):
    function: AggregateFunction
    field: Optional[str] = None  # None allowed only for count


class HavingFilter(BaseModel):
    """Post-aggregation group filter (applied client-side, research D4)."""

    function: HavingFunction
    field: Optional[str] = None  # None allowed only for count
    op: HavingOp
    value: float | int

    @field_validator("value", mode="before")
    @classmethod
    def _value_is_numeric(cls, v: object) -> object:
        # bool is an int subclass; thresholds must be genuine numbers.
        # mode="before" catches bools before pydantic coerces them to 0/1.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("having value must be numeric")
        return v


class StructuredQueryRequest(BaseModel):
    """A typed, governed query request produced by the planning stage."""

    entity: str
    operation: Operation
    fields: list[str] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    aggregate: Optional[Aggregate] = None
    relationships: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    having: Optional[HavingFilter] = None
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
            if self.aggregate.function == "ratio":
                # ratio is defined over allowlisted boolean flag columns only
                # (spec 005 FR-004; research.md Decision 3).
                if COLUMN_TYPES.get(self.aggregate.field) != "boolean":
                    raise ValueError(
                        f"ratio aggregate requires a boolean field; "
                        f"{self.aggregate.field!r} is "
                        f"{COLUMN_TYPES.get(self.aggregate.field)}")
        if self.group_by:
            if self.operation != "aggregate":
                raise ValueError(
                    "group_by is only valid with operation 'aggregate'")
            if len(self.group_by) > MAX_GROUP_BY:
                raise ValueError(
                    f"group_by supports at most {MAX_GROUP_BY} fields")
            for g in self.group_by:
                if g not in allowed:
                    raise ValueError(
                        f"group_by field {g!r} not allowed on "
                        f"{self.entity!r}")
        if self.having is not None:
            if not self.group_by:
                raise ValueError("having requires a non-empty group_by")
            if self.having.function != "count":
                if not self.having.field:
                    raise ValueError(
                        f"having {self.having.function} requires a field")
                if self.having.field not in allowed:
                    raise ValueError(
                        f"having field {self.having.field!r} not allowed on "
                        f"{self.entity!r}")
                if COLUMN_TYPES.get(self.having.field) != "numeric":
                    raise ValueError(
                        f"having {self.having.function} requires a numeric "
                        f"field; {self.having.field!r} is "
                        f"{COLUMN_TYPES.get(self.having.field)}")
        if self.order_by and self.order_by not in allowed:
            # On grouped requests order_by may also name the aggregate
            # column ("count" or "<function>_<field>"); the builder maps it.
            agg_names: set[str] = set()
            if self.group_by and self.aggregate is not None:
                fn = self.aggregate.function
                agg_names.add(fn)
                if self.aggregate.field:
                    agg_names.add(f"{fn}_{self.aggregate.field}")
                if fn == "count":
                    # GraphJin names the count column after the entity pk.
                    agg_names.add("count_ticket_id")
                    agg_names.add("count_merchant_id")
                    agg_names.add("count_agent_id")
            if self.order_by not in agg_names:
                raise ValueError(
                    f"order_by field {self.order_by!r} not allowed on "
                    f"{self.entity!r}")
        return self


class HavingApplied(BaseModel):
    """Record of a client-side post-aggregation filter (spec 005, D4)."""

    function: str
    field: Optional[str] = None
    op: str
    value: float | int
    groups_dropped: int = 0


class Evidence(BaseModel):
    """Normalized execution evidence. Answers must be grounded in this."""

    rows: list[dict] = Field(default_factory=list)
    aggregate: Optional[dict] = None
    row_count: int = 0
    # spec 005: grouped results may be truncated at the governed limit, and
    # a having post-filter may have dropped groups client-side.
    groups_truncated: bool = False
    having_applied: Optional[HavingApplied] = None


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
