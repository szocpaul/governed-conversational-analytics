"""Unit tests for grounded answering and sanitized tracing (T006).

Proves answers contain no factual value absent from execution evidence, and
that traces are sanitized (no endpoint, credentials, or full prompts).
"""
from __future__ import annotations

import json

import dspy
import pytest

from app.ai.answer_program import AnswerProgram, is_grounded
from app.api.schemas import Evidence
from app.observability.trace import Trace


# ---------------------------------------------------------------------------
# Grounding check (deterministic)
# ---------------------------------------------------------------------------

def test_grounded_answer_passes():
    ev = Evidence(rows=[], aggregate={"count": 112}, row_count=0)
    assert is_grounded("There are 112 P1 tickets.", ev) is True


def test_ungrounded_number_detected():
    ev = Evidence(rows=[], aggregate={"count": 112}, row_count=0)
    assert is_grounded("There are 999 tickets.", ev) is False


def test_empty_evidence_refusal_grounded():
    ev = Evidence(rows=[], aggregate=None, row_count=0)
    assert is_grounded("No matching data was found.", ev) is True


def test_grounded_name_from_rows():
    ev = Evidence(rows=[{"merchant_name": "BlueLinx Holdings"}], row_count=1)
    assert is_grounded("The merchant is BlueLinx Holdings.", ev) is True


def test_ungrounded_name_detected():
    ev = Evidence(rows=[{"merchant_name": "BlueLinx Holdings"}], row_count=1)
    assert is_grounded("The merchant is Acme Corp.", ev) is False


# ---------------------------------------------------------------------------
# AnswerProgram with stubbed predictor
# ---------------------------------------------------------------------------

class _Stub:
    def __init__(self, **kw):
        self._kw = kw

    def __call__(self, **kwargs):
        return dspy.Prediction(**self._kw)


def test_answer_program_returns_grounded(monkeypatch):
    prog = AnswerProgram()
    monkeypatch.setattr(prog, "answer", _Stub(answer="There are 112 tickets."))
    ev = Evidence(rows=[], aggregate={"count": 112}, row_count=0)
    out = prog(question="How many tickets?", evidence=ev)
    assert out.answer == "There are 112 tickets."


def test_answer_program_flags_ungrounded(monkeypatch):
    prog = AnswerProgram()
    monkeypatch.setattr(prog, "answer", _Stub(answer="There are 555 tickets."))
    ev = Evidence(rows=[], aggregate={"count": 112}, row_count=0)
    out = prog(question="How many tickets?", evidence=ev)
    assert out.grounded is False


# ---------------------------------------------------------------------------
# Trace sanitization
# ---------------------------------------------------------------------------

def test_trace_records_events():
    tr = Trace()
    tr.add("classified", "supported")
    tr.add("executed")
    events = tr.events
    assert events[0].event == "classified"
    assert events[1].event == "executed"


def test_trace_sanitizes_endpoint():
    tr = Trace()
    tr.add("error", "failed http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1")
    s = tr.events[0].detail
    assert "tailee6bc1" not in s
    assert "8033" not in s


def test_trace_sanitizes_bearer():
    tr = Trace()
    tr.add("error", "Authorization: Bearer abc123secret")
    assert "abc123secret" not in tr.events[0].detail


def test_trace_latency():
    tr = Trace()
    tr.add("classified")
    assert tr.latency_ms() >= 0.0


# ---------------------------------------------------------------------------
# Ratio percentage grounding (spec 005, T013)
# ---------------------------------------------------------------------------

def test_ratio_percentage_answer_grounded():
    from app.ai.answer_program import is_grounded
    ev = Evidence(
        rows=[], aggregate={"ratio_resolution_breached": 0.5041322314049587},
        row_count=0)
    assert is_grounded("50.4% of tickets breached their resolution SLA.",
                       ev, question="What percentage of tickets breached "
                                    "their resolution SLA?") is True


def test_ratio_wrong_percentage_ungrounded():
    from app.ai.answer_program import is_grounded
    ev = Evidence(
        rows=[], aggregate={"ratio_resolution_breached": 0.5041322314049587},
        row_count=0)
    # 61.2% is not the evidenced ratio.
    assert is_grounded("61.2% of tickets breached their resolution SLA.",
                       ev, question="What percentage?") is False


def test_ratio_per_group_percentages_grounded():
    from app.ai.answer_program import is_grounded
    ev = Evidence(rows=[
        {"category": "API Integrations", "ratio_resolution_breached": 0.6981},
        {"category": "Payments & Checkout", "ratio_resolution_breached": 0.793},
    ], row_count=2)
    assert is_grounded(
        "API Integrations: 69.8%; Payments & Checkout: 79.3%.", ev,
        question="Breach percentage per category?") is True


def test_null_ratio_no_fabricated_number():
    from app.ai.answer_program import is_grounded
    ev = Evidence(rows=[], aggregate={"ratio_resolution_breached": None},
                  row_count=0)
    # Any percentage claim with a null ratio is ungrounded.
    assert is_grounded("0% of tickets breached.", ev,
                       question="What percentage breached?") is False


def test_thousands_separator_number_grounded():
    """An answer restating an evidence number with a thousands separator
    ("1,807" for 1807) is grounded — the comma is formatting, not a new
    fact."""
    from app.ai.answer_program import is_grounded
    ev = Evidence(rows=[], aggregate={"count": 1807}, row_count=0)
    assert is_grounded("1,807 tickets have been closed.", ev,
                       question="How many tickets have been closed?") is True


def test_thousands_separator_wrong_number_ungrounded():
    from app.ai.answer_program import is_grounded
    ev = Evidence(rows=[], aggregate={"count": 1807}, row_count=0)
    assert is_grounded("1,708 tickets have been closed.", ev,
                       question="How many tickets have been closed?") is False
