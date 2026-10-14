"""Unit tests for the deterministic ticket_id extractor (T003).

The extractor in app/ai/routing.py is a PURE function (no LLM, no I/O) that
returns the reference ticket_id for a content_similar question, or None when
no plausible id is present. It is anchored to the pinned ticket-id shape and
must NOT false-positive on priorities (P1-P4), counts, limits, or other
numbers.
"""
from __future__ import annotations

import pytest

from app.ai.routing import extract_ticket_id


# ---------------------------------------------------------------------------
# Positive extraction (the reference id is found)
# ---------------------------------------------------------------------------

def test_extract_similar_to_bare_id():
    assert extract_ticket_id("tickets similar to 847207") == 847207


def test_extract_similar_to_ticket_id():
    assert extract_ticket_id("similar to ticket 847207") == 847207


def test_extract_find_like_id():
    assert extract_ticket_id("find tickets like 847207") == 847207


def test_extract_show_me_similar():
    assert extract_ticket_id("show me tickets similar to 847203") == 847203


def test_extract_id_anywhere_in_question():
    assert extract_ticket_id("which tickets look like 848501?") == 848501


def test_extract_five_digit_id():
    # The pinned shape allows 5-6 digit ids.
    assert extract_ticket_id("similar to ticket 84720") == 84720


# ---------------------------------------------------------------------------
# Negative: no plausible id -> None (never guesses)
# ---------------------------------------------------------------------------

def test_no_id_returns_none():
    assert extract_ticket_id("show me tickets about login problems") is None


def test_empty_string_returns_none():
    assert extract_ticket_id("") is None


def test_no_numbers_returns_none():
    assert extract_ticket_id("tickets similar to that one") is None


# ---------------------------------------------------------------------------
# No false positives on priorities, counts, limits, other numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("q", [
    "how many P1 tickets are there?",
    "list all P2 tickets",
    "show me P3 and P4 tickets",
    "count tickets with priority P1",
])
def test_priority_not_extracted(q):
    assert extract_ticket_id(q) is None


@pytest.mark.parametrize("q", [
    "show me the first 5 tickets",
    "list 10 tickets about login",
    "how many tickets are there in 2024",
    "give me at most 25 results",
])
def test_small_counts_and_limits_not_extracted(q):
    # 1-4 digit numbers (counts, limits, years) are not ticket ids.
    assert extract_ticket_id(q) is None


def test_id_like_substring_of_longer_number_not_extracted():
    # A 7+ digit number is outside the pinned 5-6 digit shape.
    assert extract_ticket_id("similar to ticket 8472071") is None


def test_priority_adjacent_to_id_still_extracts_id():
    # A real id present alongside a priority: the id wins, priority ignored.
    assert extract_ticket_id("P1 tickets similar to 847207") == 847207
