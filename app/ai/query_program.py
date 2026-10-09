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
    # Pydantic validation enforces the governed allowlist.
    return StructuredQueryRequest.model_validate(data)


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
