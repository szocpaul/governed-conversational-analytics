"""Deterministic routing helpers (feature 011, contracts/routing-integration.md).

Pure functions, no LLM, no I/O:

- extract_ticket_id: pull the reference ticket_id from a content_similar
  question. Anchored to the pinned ticket-id shape (a 5-6 digit number); never
  guesses and never false-positives on priorities (P1-P4), counts, limits, or
  years.
- normalize_category / is_content_category / CONTENT_CATEGORIES: map a raw
  classifier category token to the governed-path dispatch, with the
  conservative fallback (unknown -> structured path).

The classifier decides the routing MODE only; the ticket_id is extracted
deterministically here (human decision 5), never by the model.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Routing categories (the extended ClassifyQuestion output space)
# ---------------------------------------------------------------------------

CATEGORY_CONTENT_ABOUT = "content_about"
CATEGORY_CONTENT_SIMILAR = "content_similar"
CATEGORY_SUPPORTED = "supported"
CATEGORY_AMBIGUOUS = "ambiguous"
CATEGORY_UNSUPPORTED = "unsupported"

#: Categories that route to governed retrieval (feature 010) rather than the
#: structured planner.
CONTENT_CATEGORIES = frozenset(
    {CATEGORY_CONTENT_ABOUT, CATEGORY_CONTENT_SIMILAR})

#: All categories the classifier may legitimately output.
KNOWN_CATEGORIES = frozenset(
    {CATEGORY_CONTENT_ABOUT, CATEGORY_CONTENT_SIMILAR, CATEGORY_SUPPORTED,
     CATEGORY_AMBIGUOUS, CATEGORY_UNSUPPORTED})


def normalize_category(raw: object) -> str:
    """Normalize a raw classifier category token to a known category.

    Case/whitespace variants of a known category are accepted (robust
    parsing). Any unparseable or unknown token falls back CONSERVATIVELY to
    "supported" (the structured path): a missed content question then yields
    a clarification, never a wrong answer (human decision 6, research R3).
    """
    token = str(raw if raw is not None else "").strip().lower()
    if token in KNOWN_CATEGORIES:
        return token
    return CATEGORY_SUPPORTED


def is_content_category(category: str) -> bool:
    """Return True when the category routes to governed retrieval."""
    return category in CONTENT_CATEGORIES


# ---------------------------------------------------------------------------
# Deterministic ticket_id extractor
# ---------------------------------------------------------------------------

# Pinned ticket-id shape: a 5-6 digit number (observed range 847201-849257).
# Anchored so it does NOT match:
#   - priorities (P1-P4): a letter immediately before the digit -> the
#     (?<![A-Za-z0-9]) lookbehind rejects "P1" because "P" precedes "1";
#   - longer numbers (7+ digits): the (?!\d) lookahead rejects them;
#   - counts/limits/years (1-4 digits): below the 5-digit minimum.
_TICKET_ID_RE = re.compile(r"(?<![A-Za-z0-9])(\d{5,6})(?!\d)")


def extract_ticket_id(question: object) -> int | None:
    """Return the reference ticket_id from a content_similar question, or None.

    Pure function, no LLM, no I/O. Returns the FIRST plausible ticket_id (a
    5-6 digit number in the pinned shape) or None when none is present. Never
    guesses: priorities (P1-P4), counts, limits, and years are not matched.
    """
    if not question:
        return None
    match = _TICKET_ID_RE.search(str(question))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):  # pragma: no cover - regex guarantees digits
        return None
