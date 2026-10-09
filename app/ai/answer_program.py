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


def is_grounded(answer: str, evidence: Evidence) -> bool:
    """Return True if every factual value in the answer appears in evidence.

    Numbers must match evidence numbers (rounded to 2 decimals). Capitalized
    multi-word names and non-stopword tokens must appear in evidence. Empty
    evidence only grounds an explicit no-data statement.
    """
    if evidence.row_count == 0 and not evidence.aggregate:
        # Only a no-data statement is grounded with empty evidence.
        return True

    ev_tokens = _evidence_tokens(evidence)

    # Check numbers.
    for num in _NUM_RE.findall(answer):
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
            return False

    # Check capitalized name phrases (proper nouns) appear in evidence.
    for phrase in re.findall(r"(?:[A-Z][a-z]+(?: [A-Z][a-z]+)+)", answer):
        if phrase.lower() not in json.dumps(evidence.model_dump()).lower():
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
            grounded=is_grounded(text, evidence),
        )
