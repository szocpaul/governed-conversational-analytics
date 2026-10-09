"""Optimizer metric tests (spec 004, T005).

Written BEFORE app/ai/optimization.py. text_to_query_metric returns 1.0 ONLY
when all mandatory checks pass: valid structured output, read-only
policy-allowed request, successful governed execution, expected normalized
result, and zero prohibited effect/disclosure. Otherwise 0.0 (no partial
credit).
"""
from __future__ import annotations

import dspy
import pytest

from app.ai import optimization


def _example(request, result):
    return dspy.Example(
        question="q",
        expected_request=request,
        expected_result=result,
    ).with_inputs("question")


def _pred(request=None, raw=None, execution_result=None, executed=True,
          prohibited=False, disclosed=False):
    """A minimal prediction-like object for the metric."""
    p = dspy.Prediction()
    p.request = request
    p.raw_output = raw
    p.execution_result = execution_result
    p.executed = executed
    p.prohibited_effect = prohibited
    p.disclosure = disclosed
    return p


GOOD_REQ = {"entity": "tickets", "operation": "aggregate",
            "aggregate": {"function": "count", "field": None},
            "filters": [], "limit": 100}


def test_metric_one_when_all_checks_pass():
    ex = _example(GOOD_REQ, {"count": 2057})
    pred = _pred(request=GOOD_REQ, execution_result={"count": 2057})
    assert optimization.text_to_query_metric(ex, pred) == 1.0


def test_metric_zero_on_invalid_structure():
    ex = _example(GOOD_REQ, {"count": 2057})
    pred = _pred(request={"entity": "users", "operation": "list"},
                 execution_result={"count": 2057})
    assert optimization.text_to_query_metric(ex, pred) == 0.0


def test_metric_zero_on_write_request():
    ex = _example(GOOD_REQ, {"count": 2057})
    bad = dict(GOOD_REQ, operation="delete")
    pred = _pred(request=bad, execution_result={"count": 2057})
    assert optimization.text_to_query_metric(ex, pred) == 0.0


def test_metric_zero_on_result_mismatch():
    ex = _example(GOOD_REQ, {"count": 2057})
    pred = _pred(request=GOOD_REQ, execution_result={"count": 999})
    assert optimization.text_to_query_metric(ex, pred) == 0.0


def test_metric_zero_when_not_executed():
    ex = _example(GOOD_REQ, {"count": 2057})
    pred = _pred(request=GOOD_REQ, execution_result=None, executed=False)
    assert optimization.text_to_query_metric(ex, pred) == 0.0


def test_metric_zero_on_prohibited_effect():
    ex = _example(GOOD_REQ, {"count": 2057})
    pred = _pred(request=GOOD_REQ, execution_result={"count": 2057},
                 prohibited=True)
    assert optimization.text_to_query_metric(ex, pred) == 0.0


def test_metric_zero_on_disclosure():
    ex = _example(GOOD_REQ, {"count": 2057})
    pred = _pred(request=GOOD_REQ, execution_result={"count": 2057},
                 disclosed=True)
    assert optimization.text_to_query_metric(ex, pred) == 0.0


def test_metric_zero_on_missing_request():
    ex = _example(GOOD_REQ, {"count": 2057})
    pred = _pred(request=None, execution_result={"count": 2057})
    assert optimization.text_to_query_metric(ex, pred) == 0.0
