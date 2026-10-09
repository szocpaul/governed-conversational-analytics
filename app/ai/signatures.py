"""DSPy typed signatures for the conversational query pipeline.

Idiomatic DSPy: typed Signature subclasses (docstring is the instruction),
composed into dspy.Module programs with dspy.Predict / dspy.ChainOfThought.
No hard-coded prompt strings, no arbitrary SQL output. The planner emits a
typed StructuredQueryRequest JSON, never free-form SQL.
"""
from __future__ import annotations

import dspy

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class ClassifyQuestion(dspy.Signature):
    """Classify a natural-language ITSM analytics question.

    Decide whether the question is a supported analytical question over the
    governed ITSM dataset (tickets, merchants, agents), is materially
    ambiguous and needs clarification, or is unsupported/out of scope.
    """

    question: str = dspy.InputField(desc="the user's natural-language question")
    category: str = dspy.OutputField(
        desc="one of: supported, ambiguous, unsupported")
    rationale: str = dspy.OutputField(
        desc="one short sentence explaining the classification")


# ---------------------------------------------------------------------------
# Query planning
# ---------------------------------------------------------------------------


class PlanQuery(dspy.Signature):
    """Plan a typed, governed GraphQL query request for a supported question.

    Output a JSON object for a StructuredQueryRequest over the governed ITSM
    schema. Entities and fields are strictly limited to the allowlist:

    - tickets: ticket_id, merchant_id, category, sub_category, priority,
      created_at, is_legacy, assigned_agent_id, category_mismatch,
      first_response_at, closed_at, ttfr_hours, resolution_hours,
      response_breached, resolution_breached, is_reopened, is_reopen_child,
      is_incident_ticket, csat_score
    - merchants: merchant_id, merchant_name, sector, tier, region
    - agents: agent_id, agent_name, tier, primary_category, shift_region,
      efficiency_multiplier

    Rules:
    - operation is "list" (return rows) or "aggregate" (count/sum/avg/min/max).
    - filters use ops: eq, ne, gt, gte, lt, lte, in, like.
    - Use created_at with gte/lt for time ranges (ISO dates).
    - relationships may include merchants and/or agents from tickets.
    - limit must be between 1 and 100.
    - NEVER output SQL. Output ONLY the JSON request object.
    """

    question: str = dspy.InputField(desc="a supported analytical question")
    request_json: str = dspy.OutputField(
        desc=(
            "a single JSON object matching StructuredQueryRequest exactly; "
            "no SQL, no prose, no code fences. Shape: {\"entity\": "
            "\"tickets\", \"operation\": \"aggregate\", \"aggregate\": "
            "{\"function\": \"count\", \"field\": null}, \"filters\": "
            "[{\"field\": \"priority\", \"op\": \"eq\", \"value\": "
            "\"P1\"}], \"limit\": 100}. For a list operation use "
            "\"operation\": \"list\" with \"fields\": [...] and no "
            "\"aggregate\" key."
        )
    )


# ---------------------------------------------------------------------------
# Grounded answer
# ---------------------------------------------------------------------------


class GroundAnswer(dspy.Signature):
    """Answer the question using ONLY the provided execution evidence.

    Every factual value in the answer MUST come from the evidence. If the
    evidence is empty or insufficient, say that no matching data was found;
    do NOT invent numbers, names, or dates.
    """

    question: str = dspy.InputField(desc="the user's question")
    evidence: str = dspy.InputField(
        desc="JSON of normalized rows/aggregate returned by the governed query")
    answer: str = dspy.OutputField(
        desc="a concise answer grounded strictly in the evidence")
