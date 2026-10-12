"""T005: Unit tests for the typed DSPy text-generation program (stubbed LM).

The LM is stubbed with dspy.utils.DummyLM (scripted JSON responses); the
parsing, zero-tolerance acceptance, and bounded-retry logic under test is real.
The shipped artifact only ever comes from a real recorded run (research R11).
"""
from __future__ import annotations

import importlib.util
import json
import os

import dspy
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MODULE_PATH = os.path.join(REPO_ROOT, "app", "ai", "text_generation.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("app.ai.text_generation", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so pydantic resolves forward references
    # (from __future__ import annotations) against the live module.
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def tg():
    return _load_module()


BATCH_TICKETS = [
    {"ticket_id": 101, "category": "Account Access", "sub_category": "Password Reset",
     "priority": "P2", "is_open": False},
    {"ticket_id": 102, "category": "Payments & Checkout", "sub_category": "Card Declines",
     "priority": "P1", "is_open": False},
    {"ticket_id": 103, "category": "Notifications", "sub_category": "Email Delivery Failure",
     "priority": "P3", "is_open": True},
    {"ticket_id": 104, "category": "API Integrations", "sub_category": "Rate Limiting",
     "priority": "P4", "is_open": False},
    {"ticket_id": 105, "category": "Fulfilment & Logistics", "sub_category": "Tracking Updates",
     "priority": "P2", "is_open": True},
]


def _valid_entries():
    return [
        {"ticket_id": 101, "short_description": "The password reset email never arrives.",
         "description": "The merchant reports users cannot reset their password. The reset email never arrives. Multiple users are affected.",
         "resolution_notes": "The mail queue was stuck. The team flushed the queue. Reset emails now arrive."},
        {"ticket_id": 102, "short_description": "Customer cards are declined at checkout.",
         "description": "The merchant reports a spike in card declines at checkout. The issue started this morning. Revenue is directly impacted.",
         "resolution_notes": "The acquirer endpoint was misconfigured. The team corrected the endpoint. Decline rates returned to normal."},
        {"ticket_id": 103, "short_description": "Order confirmation emails are not delivered.",
         "description": "The merchant reports order confirmation emails are missing. Customers call support instead. The issue affects all templates.",
         "resolution_notes": None},
        {"ticket_id": 104, "short_description": "API calls hit the rate limit intermittently.",
         "description": "The merchant reports intermittent rate limit errors on the API. Retries eventually succeed. The impact is minor.",
         "resolution_notes": "The client was not backing off. The merchant added backoff. Errors stopped."},
        {"ticket_id": 105, "short_description": "Tracking updates stop after the first scan.",
         "description": "The merchant reports tracking updates stall after the first scan. Customers see stale statuses. The carrier feed appears delayed.",
         "resolution_notes": None},
    ]


def _program_with_answers(tg, answers):
    lm = dspy.utils.DummyLM(answers, adapter=dspy.JSONAdapter())
    dspy.configure(lm=lm, adapter=dspy.JSONAdapter())
    return tg.TicketTextProgram(max_retries=2)


# ---------------------------------------------------------------------------
# Strict pydantic entry model
# ---------------------------------------------------------------------------

def test_entry_model_strict_types(tg):
    entry = tg.TicketTextEntry(
        ticket_id=1, short_description="a", description="b", resolution_notes=None)
    assert entry.resolution_notes is None
    with pytest.raises(Exception):
        tg.TicketTextEntry(ticket_id="1", short_description="a",
                           description="b", resolution_notes=None)


def test_entry_model_requires_all_keys(tg):
    with pytest.raises(Exception):
        tg.TicketTextEntry(ticket_id=1, short_description="a", description="b")


def test_prompt_version_constant(tg):
    assert tg.PROMPT_VERSION == "1"


# ---------------------------------------------------------------------------
# Batch acceptance (zero tolerance)
# ---------------------------------------------------------------------------

def test_valid_batch_accepted(tg):
    program = _program_with_answers(tg, [{"entries": json.dumps(_valid_entries())}])
    entries = program.generate_batch(BATCH_TICKETS)
    assert [e.ticket_id for e in entries] == [101, 102, 103, 104, 105]
    assert entries[2].resolution_notes is None
    assert entries[4].resolution_notes is None
    assert all(isinstance(e, tg.TicketTextEntry) for e in entries)


def test_malformed_json_rejected(tg):
    program = _program_with_answers(tg, [{"entries": "[{not valid json"}] * 3)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)


def test_ticket_id_missing_rejected(tg):
    entries = _valid_entries()[:4]
    program = _program_with_answers(tg, [{"entries": json.dumps(entries)}] * 3)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)


def test_ticket_id_extra_rejected(tg):
    entries = _valid_entries() + [
        {"ticket_id": 999, "short_description": "x", "description": "y",
         "resolution_notes": None}]
    program = _program_with_answers(tg, [{"entries": json.dumps(entries)}] * 3)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)


def test_ticket_id_duplicate_rejected(tg):
    entries = _valid_entries()
    entries[4] = dict(entries[3])  # duplicate 104, missing 105
    program = _program_with_answers(tg, [{"entries": json.dumps(entries)}] * 3)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)


def test_resolution_notes_non_null_for_open_ticket_rejected(tg):
    entries = _valid_entries()
    entries[2]["resolution_notes"] = "Fixed prematurely."  # ticket 103 is open
    program = _program_with_answers(tg, [{"entries": json.dumps(entries)}] * 3)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)


def test_resolution_notes_null_for_closed_ticket_rejected(tg):
    entries = _valid_entries()
    entries[0]["resolution_notes"] = None  # ticket 101 is closed
    program = _program_with_answers(tg, [{"entries": json.dumps(entries)}] * 3)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)


def test_empty_string_field_rejected(tg):
    entries = _valid_entries()
    entries[1]["short_description"] = "   "
    program = _program_with_answers(tg, [{"entries": json.dumps(entries)}] * 3)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)


# ---------------------------------------------------------------------------
# Bounded retries
# ---------------------------------------------------------------------------

def test_batch_retried_then_succeeds(tg):
    bad = [{"entries": "[{broken"}]
    good = [{"entries": json.dumps(_valid_entries())}]
    program = _program_with_answers(tg, bad + good)
    entries = program.generate_batch(BATCH_TICKETS)
    assert len(entries) == 5


def test_batch_retries_exhausted_raises(tg):
    program = _program_with_answers(tg, [{"entries": "[{broken"}] * 3)
    with pytest.raises(tg.BatchGenerationError) as excinfo:
        program.generate_batch(BATCH_TICKETS)
    assert "101" in str(excinfo.value)  # names the failing batch


def test_max_retries_configurable(tg):
    lm = dspy.utils.DummyLM([{"entries": "[{broken"}] * 5, adapter=dspy.JSONAdapter())
    dspy.configure(lm=lm, adapter=dspy.JSONAdapter())
    program = tg.TicketTextProgram(max_retries=0)
    with pytest.raises(tg.BatchGenerationError):
        program.generate_batch(BATCH_TICKETS)
