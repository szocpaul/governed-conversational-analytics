"""DSPy query program: classification + typed query planning (T003).

Idiomatic DSPy Module composing two typed predictors. The planner emits a
JSON StructuredQueryRequest (never SQL); parsing back into the typed model is
deterministic and validates against the governed allowlist.
"""
from __future__ import annotations

import json
import re

import dspy
from pydantic import ValidationError as PydanticValidationError

from app.ai.signatures import ClassifyQuestion, PlanQuery
from app.api.schemas import StructuredQueryRequest
from app.security.errors import UnsupportedQuestionError

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class UnsupportedShapeError(ValueError):
    """Planner emitted a query shape the governed pipeline does not support.

    Raised for GROUP BY/HAVING/joins and other unsupported keys, and for
    order_by shapes that cannot be normalized to a single field. Mapped to
    the stable "unsupported" category; never reaches GraphJin.
    """


def parse_request_json(raw: str) -> StructuredQueryRequest:
    """Parse planner output into a validated StructuredQueryRequest.

    Raises ValueError on non-JSON, SQL-looking, or policy-violating output.
    """
    if raw is None:
        raise ValueError("empty planner output")
    text = str(raw).strip()
    # Strip markdown code fences if present.
    text = _FENCE_RE.sub("", text).strip()
    # Extract the first JSON object if the model added prose around it.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("planner output is not a JSON object")
    candidate = text[start:end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"planner output is not valid JSON: {exc}") from exc
    data = _normalize_shape(data)
    # Pydantic validation enforces the governed allowlist.
    return StructuredQueryRequest.model_validate(data)


# Keys that indicate a query shape the governed pipeline does NOT support.
# They must never be silently dropped: a request whose semantics depend on
# them would otherwise be rewritten into a different (wrong) query (F2/F8).
_UNSUPPORTED_KEYS = {
    "group_by", "groupby", "group", "having", "distinct", "join", "joins",
    "subquery", "union", "order_by_fields",
}

_ALLOWED_KEYS = {
    "entity", "operation", "fields", "filters", "aggregate",
    "relationships", "order_by", "order_dir", "limit",
}


def _normalize_shape(data: dict) -> dict:
    """Adapt common planner output variants to the canonical shape.

    The model sometimes emits an "aggregations" array (with optional "alias")
    instead of the singular "aggregate" object, and sometimes emits order_by
    as a list of {"field", "direction"} objects (F7). Normalize those
    deterministically. Any key that expresses an unsupported query shape
    (GROUP BY, HAVING, joins, ...) raises ValueError so the request is
    rejected as unsupported BEFORE any GraphJin call, never silently dropped.
    """
    if not isinstance(data, dict):
        raise ValueError("planner output is not a JSON object")

    # Reject unsupported query shapes explicitly (F1/F2/F8). Silently
    # stripping these would change the query's meaning.
    present_unsupported = _UNSUPPORTED_KEYS & {str(k).lower() for k in data}
    if present_unsupported:
        raise UnsupportedShapeError(
            "unsupported query shape: "
            + ", ".join(sorted(present_unsupported)))

    if "aggregate" not in data and isinstance(data.get("aggregations"), list):
        aggs = data["aggregations"]
        if aggs and isinstance(aggs[0], dict):
            first = aggs[0]
            data["aggregate"] = {
                "function": first.get("function"),
                "field": first.get("field"),
            }
        data.pop("aggregations", None)

    # Normalize order_by emitted as a list of {"field", "direction"} (F7).
    order_by = data.get("order_by")
    if isinstance(order_by, list):
        if len(order_by) != 1 or not isinstance(order_by[0], dict):
            raise UnsupportedShapeError(
                "unsupported order_by shape: expected a single field")
        spec = order_by[0]
        data["order_by"] = spec.get("field")
        direction = str(spec.get("direction", "asc")).lower()
        if direction not in ("asc", "desc"):
            raise UnsupportedShapeError(
                f"unsupported order direction: {direction!r}")
        data["order_dir"] = direction
    elif isinstance(order_by, dict):
        spec = order_by
        data["order_by"] = spec.get("field")
        direction = str(spec.get("direction", "asc")).lower()
        if direction not in ("asc", "desc"):
            raise UnsupportedShapeError(
                f"unsupported order direction: {direction!r}")
        data["order_dir"] = direction

    return {k: v for k, v in data.items() if k in _ALLOWED_KEYS}


class QueryProgram(dspy.Module):
    """Classify a question and, if supported, plan a typed governed request."""

    def __init__(self):
        super().__init__()
        self.classify = dspy.Predict(ClassifyQuestion)
        self.plan = dspy.Predict(PlanQuery)

    def forward(self, question: str) -> dspy.Prediction:
        cls = self.classify(question=question)
        category = str(cls.category).strip().lower()
        if category != "supported":
            return dspy.Prediction(
                classification=category,
                rationale=str(cls.rationale),
                request=None,
            )
        planned = self.plan(question=question)
        try:
            request = parse_request_json(planned.request_json)
        except UnsupportedShapeError as exc:
            # Unsupported query shape (GROUP BY, HAVING, multi-field order):
            # stable "unsupported" category, zero GraphJin calls (F1/F2/F8).
            raise UnsupportedQuestionError(str(exc)) from exc
        except PydanticValidationError as exc:
            # Valid JSON that violates the governed schema (e.g. a
            # relationship field placed in `fields`): the planned request
            # cannot execute as governed. Map to the stable "unsupported"
            # category instead of surfacing a raw model dependency
            # failure (F7). Non-JSON output still raises ValueError, which
            # the caller treats as a model dependency failure.
            raise UnsupportedQuestionError(
                "planned request violates the governed schema") from exc
        return dspy.Prediction(
            classification="supported",
            rationale=str(cls.rationale),
            request=request,
        )
