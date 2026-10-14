"""DSPy typed signatures for the conversational query pipeline.

Idiomatic DSPy: typed Signature subclasses (docstring is the instruction),
composed into dspy.Module programs with dspy.Predict / dspy.ChainOfThought.
No hard-coded prompt strings, no arbitrary SQL output. The planner emits a
typed StructuredQueryRequest JSON, never free-form SQL.
"""
from __future__ import annotations

import dspy

# Versioned instruction marker: bumped on any change to a signature docstring
# or output field (house discipline; feature 011 extended ClassifyQuestion).
PROMPT_VERSION = "3"

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class ClassifyQuestion(dspy.Signature):
    """Classify a natural-language ITSM analytics question.

    Route the question to exactly ONE category so the governed pipeline can
    handle it: content_about, content_similar, content_count, supported,
    ambiguous, or unsupported.

    A question is CONTENT_ABOUT when it asks to FIND tickets by what they are
    ABOUT — their text content (the subject, symptoms, or situation described
    in the ticket) — rather than by a structured column value. This includes
    DEEP PARAPHRASES that share no keywords with the tickets: route by
    MEANING, not by word shape. Examples: "tickets about login problems",
    "customers unable to complete a purchase because their card was
    rejected", "people getting locked out and unable to prove who they are at
    sign-in", "slow to notify users".

    A question is CONTENT_SIMILAR when it asks for tickets SIMILAR to a
    referenced ticket (a ticket id is present or implied). Examples:
    "tickets similar to 847207", "find tickets like 847203".

    A question is CONTENT_COUNT when it asks for a COUNT over a TOPIC — how
    many tickets are ABOUT something (their text content), not a structured
    column value. Examples: "how many tickets about login", "how many tickets
    are about sign-in problems", "how many tickets mention password resets".
    The topic lives in the ticket text, so a structured count cannot answer
    it; route it to content_count, NOT supported. A question asking for a
    LIST of tickets about a topic is content_about, NOT content_count.

    A question is SUPPORTED when it can be answered by ONE governed
    structured query: a single list of rows, a single aggregate (count/sum/
    avg/min/max/ratio) with optional filters and ordering, or a grouped
    breakdown (group_by over 1-3 fields with one aggregate, optionally
    filtered per-group with having). A COUNT, AGGREGATE, or GROUPED BREAKDOWN
    question is SUPPORTED only when the count/aggregate is over a STRUCTURED
    column value: "how many P1 tickets" or "how many tickets in category X"
    is supported. A COUNT over a TOPIC ("how many tickets are about login")
    is content_count, NOT supported, because the topic lives in the text.

    Classify as AMBIGUOUS when the question asks for several things at once
    (multi-part, e.g. "which agent is best AND how many tickets"), because a
    single governed query cannot answer every part and no part may be
    silently dropped.

    Classify as UNSUPPORTED when the question needs query shapes the schema
    cannot express: joins across entities in one result, subqueries, unions,
    or data outside the governed dataset.

    When you are uncertain whether a question is content_about, content_count,
    or a structured analytical question, prefer SUPPORTED (the conservative
    default): a missed content question then yields a clarification rather
    than a wrong answer.
    """

    question: str = dspy.InputField(desc="the user's natural-language question")
    category: str = dspy.OutputField(
        desc="one of: content_about, content_similar, content_count, "
             "supported, ambiguous, unsupported")
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
    - operation is "list" (return rows) or "aggregate" (count/sum/avg/min/max/
      ratio).
    - filters use ops: eq, ne, gt, gte, lt, lte, in, like, is_null,
      is_not_null. The is_null/is_not_null ops take NO value (null).
      Missing-value filtering: "open" tickets are closed_at is_null;
      "closed" tickets are closed_at is_not_null; "no assigned agent" is
      assigned_agent_id is_null.
    - Use created_at with gte/lt for time ranges (ISO dates).
    - relationships may include merchants and/or agents from tickets.
    - limit must be between 1 and 100.
    - order_by is a single field NAME (string), order_dir is "asc" or "desc".
      For "highest/lowest/most/least/newest/oldest" questions you MUST set
      order_by on the relevant field with the matching direction and a small
      limit, so the returned row is the actual extremum.
    - avg and sum are ONLY valid on numeric fields (ttfr_hours,
      resolution_hours, csat_score, efficiency_multiplier).
    - For ratio/percentage questions over a boolean flag (e.g. "what
      percentage of tickets breached their resolution SLA"), use the
      "ratio" aggregate with the flag as field: {"function": "ratio",
      "field": "resolution_breached"}. ratio is ONLY valid on boolean
      fields (is_legacy, category_mismatch, response_breached,
      resolution_breached, is_reopened, is_reopen_child,
      is_incident_ticket). The result is a value in [0, 1]; a null result
      means the base set is empty. ratio also works with group_by for a
      per-group percentage.
    - Filter values must match the column type: integer ids take integers,
      boolean flags take true/false, text fields take strings. Never filter
      an id field with a name. Only the is_null/is_not_null ops carry a null
      value; every other op requires a typed non-null value.
    - Grouped breakdowns ARE supported: for "by category/per sector/which
      group has the most" questions, use operation "aggregate" with
      "group_by": [1-3 allowlisted fields] and one aggregate. On grouped
      requests order_by may name a grouping field or the string "count"
      (the aggregate column) — use order_by "count", order_dir "desc" for
      "which group has the most" questions.
    - An optional "having" object filters groups AFTER aggregation:
      {"function": "count"|"sum"|"avg"|"min"|"max", "field": null or an
      allowlisted numeric field, "op": "eq"|"ne"|"gt"|"gte"|"lt"|"lte",
      "value": <number>}. having is ONLY valid with a non-empty group_by
      (e.g. "merchants with more than 50 tickets" -> group_by
      ["merchant_id"], having {"function": "count", "field": null,
      "op": "gt", "value": 50}).
    - NEVER emit joins, subqueries, union, or a bare "distinct" key.
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

    The evidence has two forms: "rows" (a list of result rows) and
    "aggregate" (a computed value such as {"count": 112} or
    {"avg_resolution_hours": 2.34}). A non-null aggregate value IS data:
    when it is present, report that value; never claim no data was found.
    Only say no matching data was found when rows is empty AND every
    aggregate value is null.

    Grouped evidence: each row in "rows" is one group with its grouping
    field values and aggregate column (e.g. {"category": "Payments &
    Checkout", "count_ticket_id": 483}). Answer per-group questions from
    these rows only; when "groups_truncated" is true, say the breakdown may
    be incomplete.

    Ratio evidence: an aggregate like {"ratio_resolution_breached":
    0.5041} is a fraction in [0, 1]; format it as a percentage (50.4%).
    NEVER invent numerator/denominator counts for a ratio — report only
    the percentage the evidence carries. A null ratio means the base set
    is empty; say the ratio is undefined instead of stating a number.
    """

    question: str = dspy.InputField(desc="the user's question")
    evidence: str = dspy.InputField(
        desc="JSON of normalized rows/aggregate returned by the governed query")
    answer: str = dspy.OutputField(
        desc="a concise answer grounded strictly in the evidence")
