"""DSPy query program: classification + typed query planning (T003).

Idiomatic DSPy Module composing two typed predictors. The planner emits a
JSON StructuredQueryRequest (never SQL); parsing back into the typed model is
deterministic and validates against the governed allowlist.
"""
from __future__ import annotations

import json
import re

import dspy

from app.ai.signatures import ClassifyQuestion, PlanQuery
from app.api.schemas import StructuredQueryRequest

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


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


def _normalize_shape(data: dict) -> dict:
    """Adapt common planner output variants to the canonical shape.

    The model sometimes emits an "aggregations" array (with optional "alias")
    instead of the singular "aggregate" object. Normalize deterministically.
    """
    if not isinstance(data, dict):
        raise ValueError("planner output is not a JSON object")
    if "aggregate" not in data and isinstance(data.get("aggregations"), list):
        aggs = data["aggregations"]
        if aggs and isinstance(aggs[0], dict):
            first = aggs[0]
            data["aggregate"] = {
                "function": first.get("function"),
                "field": first.get("field"),
            }
        data.pop("aggregations", None)
    # Drop unknown helper keys the model may add (e.g. alias) is handled by
    # pydantic's default ignore of extra fields only if configured; strip them.
    allowed_keys = {
        "entity", "operation", "fields", "filters", "aggregate",
        "relationships", "order_by", "order_dir", "limit",
    }
    return {k: v for k, v in data.items() if k in allowed_keys}


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
        request = parse_request_json(planned.request_json)
        return dspy.Prediction(
            classification="supported",
            rationale=str(cls.rationale),
            request=request,
        )
