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
