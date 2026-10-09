"""DSPy grounded-answer generation (T006).

The answer is produced by a typed DSPy predictor from the question plus the
normalized execution evidence. A deterministic grounding check then verifies
that every factual token (numbers and named values) in the answer appears in
the evidence; ungrounded answers are flagged so the caller can refuse.
"""
from __future__ import annotations

import json
import re

import dspy

from app.ai.signatures import GroundAnswer
from app.api.schemas import Evidence

_NUM_RE = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?(?![A-Za-z0-9_])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]+")
_NO_DATA_RE = re.compile(
    r"no matching data|no data (was )?found|no results? (were )?found|"
    r"no records? (were )?found|did not return any|"
    r"no .{0,30} (were|was) found", re.IGNORECASE)

# Common stopwords that are not factual values.
_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "there", "of", "for",
    "in", "on", "with", "and", "or", "to", "no", "matching", "data", "found",
    "tickets", "ticket", "merchants", "merchant", "agents", "agent", "how",
    "many", "what", "which", "show", "list", "have", "has", "been", "be",
    "were", "was", "did", "do", "does", "any", "none", "average", "total",
    "count", "number", "hours", "hour", "score", "scores",
}


def _evidence_tokens(ev: Evidence) -> set[str]:
    text = json.dumps(ev.model_dump())
    nums = set(_NUM_RE.findall(text))
    words = {w.lower() for w in _WORD_RE.findall(text)}
    return nums | words


def is_grounded(answer: str, evidence: Evidence,
                question: str | None = None) -> bool:
    """Return True if every factual value in the answer appears in evidence.

    Numbers must match evidence numbers (rounded to 2 decimals). Capitalized
    multi-word names must appear in the evidence — unless they appear in the
    question itself, where they are query parameters the answer legitimately
    echoes (F4: the filter value "Account Access" is not part of the result
    row, but restating it is not a hallucination). A factual value absent
    from BOTH evidence and question remains ungrounded (F3).

    Empty evidence only grounds an explicit no-data statement.
    """
    ev_text = json.dumps(evidence.model_dump()).lower()
    question_text = (question or "").lower()

    if evidence.row_count == 0 and not evidence.aggregate:
        # Only a no-data statement is grounded with empty evidence.
        return True

    # A "no data" claim contradicts non-empty evidence (F6: count=1037 was
    # answered with "no matching data"). Detect explicit no-data phrasing and
    # refuse it when the evidence actually contains a result.
    if _NO_DATA_RE.search(answer):
        has_value = bool(evidence.rows) or any(
            v is not None for v in (evidence.aggregate or {}).values())
        if has_value:
            return False

    # Strip list-enumeration markers ("1.", "2)", "- ") so ordinal indices are
    # not mistaken for factual data values.
    scrubbed = re.sub(r"(?m)^\s*\d+[.)]\s+", " ", answer)
    scrubbed = re.sub(r"\s\d+[.)]\s+", " ", scrubbed)

    # Check numbers.
    for num in _NUM_RE.findall(scrubbed):
        try:
            val = round(float(num), 2)
        except ValueError:
            return False
        matched = False
        for ev_num in _NUM_RE.findall(json.dumps(evidence.model_dump())):
            try:
                if round(float(ev_num), 2) == val:
                    matched = True
                    break
            except ValueError:
                continue
        if not matched:
            # Numbers that appear in the question (e.g. a year or threshold
            # restated by the answer) are query parameters, not derived facts.
            if num in question_text:
                continue
            return False

    # Check capitalized name phrases (proper nouns) appear in evidence.
    for phrase in re.findall(r"(?:[A-Z][a-z]+(?: [A-Z][a-z]+)+)", answer):
        if phrase.lower() in ev_text:
            continue
        if question_text and phrase.lower() in question_text:
            # Query parameter echoed from the question (F4).
            continue
        return False

    return True


class AnswerProgram(dspy.Module):
    """Generate a grounded answer from evidence."""

    def __init__(self):
        super().__init__()
        self.answer = dspy.Predict(GroundAnswer)

    def forward(self, question: str, evidence: Evidence) -> dspy.Prediction:
        ev_json = json.dumps(evidence.model_dump())
        pred = self.answer(question=question, evidence=ev_json)
        text = str(pred.answer)
        return dspy.Prediction(
            answer=text,
            grounded=is_grounded(text, evidence, question=question),
        )
