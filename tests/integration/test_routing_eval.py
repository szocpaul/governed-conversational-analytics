"""T015: Deterministic routing-evaluation isolation checks (feature 011).

These tests are DETERMINISTIC (no live model, no stack): they verify the
routing case files are physically separate with disjoint IDs, the leakage
guard rejects any held-out ID in a routing trainset, the routing metric
scores canary cases correctly, and the committed optimization-run record
contains only development case IDs. The live tuning run and held-out eval
are quickstart procedures, not pytest.
"""
from __future__ import annotations

import json
import os

import pytest

from app.ai import optimization as opt
from app.ai.routing import extract_ticket_id, normalize_category
from evaluation import metrics
from evaluation.schemas import load_dev_cases, load_held_out_cases

_REPO = os.path.join(os.path.dirname(__file__), "..", "..")
_OPT_RUN = os.path.join(_REPO, "artifacts", "optimization-run.json")


# ---------------------------------------------------------------------------
# 1. Physical separation + disjoint IDs
# ---------------------------------------------------------------------------

def test_routing_case_files_physically_separate_and_disjoint():
    dev = load_dev_cases()
    held = load_held_out_cases()
    dev_ids = set(dev.ids)
    held_ids = set(held.ids)
    # Disjoint across the two files (no ID appears in both).
    assert not (dev_ids & held_ids), "dev/held-out case IDs must be disjoint"
    # The routing cases exist in both files with the expected counts.
    dev_routing = [c for c in dev.cases if c.category.startswith("route_")]
    held_routing = [c for c in held.cases
                    if c.category.startswith("route_")
                    or c.category == "security_content"]
    assert len(dev_routing) >= 8, "expected >= 8 development routing cases"
    assert len(held_routing) >= 10, "expected >= 10 held-out routing cases"


def test_routing_categories_present():
    dev = load_dev_cases()
    held = load_held_out_cases()
    dev_cats = {c.category for c in dev.cases if c.category.startswith("route_")}
    assert {"route_content_about", "route_content_similar",
            "route_structured", "route_unsupported"} <= dev_cats
    # Held-out includes security content cases.
    assert any(c.category == "security_content" for c in held.cases)


# ---------------------------------------------------------------------------
# 2. Leakage guard rejects held-out IDs in a routing trainset
# ---------------------------------------------------------------------------

def test_routing_trainset_contains_only_dev_ids():
    trainset = opt.build_routing_trainset()
    held_ids = set(load_held_out_cases().ids)
    assert trainset, "expected a non-empty routing trainset"
    for e in trainset:
        assert e.case_id not in held_ids
        assert e.case_id.startswith("DEV-")


def test_leakage_guard_rejects_held_out_id():
    held_ids = list(load_held_out_cases().ids)
    with pytest.raises(AssertionError):
        opt.assert_no_held_out_leakage(held_ids[:1])


# ---------------------------------------------------------------------------
# 3. Routing metric canary cases (1.0 / 0.0)
# ---------------------------------------------------------------------------

class _Ex:
    def __init__(self, route, question, ticket_id=None):
        self.expected_route = route
        self.question = question
        self.expected_ticket_id = ticket_id


class _Pred:
    def __init__(self, category):
        self.category = category


def test_routing_metric_correct_content_about():
    e = _Ex("content_about", "tickets about login")
    assert opt.routing_metric(e, _Pred("content_about")) == 1.0


def test_routing_metric_wrong_category():
    e = _Ex("content_about", "tickets about login")
    assert opt.routing_metric(e, _Pred("supported")) == 0.0


def test_routing_metric_content_similar_requires_matching_id():
    e = _Ex("content_similar", "tickets similar to 847207", ticket_id=847207)
    assert opt.routing_metric(e, _Pred("content_similar")) == 1.0
    # Wrong reference id in the question -> 0.0.
    e2 = _Ex("content_similar", "tickets similar to 847208", ticket_id=847207)
    assert opt.routing_metric(e2, _Pred("content_similar")) == 0.0


def test_routing_metric_unparseable_is_not_correct():
    e = _Ex("content_about", "tickets about login")
    # Unparseable output falls back to structured; not a correct content route.
    assert opt.routing_metric(e, _Pred("gibberish")) == 0.0


def test_metrics_routing_accuracy_and_false_routing():
    per_case = [
        {"expected_route": "supported", "predicted_category": "supported",
         "routing_correct": 1.0},
        {"expected_route": "supported", "predicted_category": "content_about",
         "routing_correct": 0.0},
        {"expected_route": "content_about",
         "predicted_category": "content_about", "routing_correct": 1.0},
    ]
    assert metrics.routing_accuracy(per_case) == round(2 / 3, 4)
    assert metrics.false_routing_rate(per_case) == 0.5
    assert metrics.routing_accuracy([]) is None
    assert metrics.false_routing_rate([]) is None


# ---------------------------------------------------------------------------
# 4. Committed optimization-run records only development case IDs
# ---------------------------------------------------------------------------

def test_optimization_run_records_only_dev_ids():
    assert os.path.exists(_OPT_RUN), "optimization-run.json must exist"
    with open(_OPT_RUN) as f:
        run = json.load(f)
    held_ids = set(load_held_out_cases().ids)
    for key in ("input_case_ids", "accepted_demo_ids"):
        ids = run.get(key) or []
        for cid in ids:
            assert cid not in held_ids, f"{key} contains held-out ID {cid}"
            assert cid.startswith("DEV-"), f"{key} contains non-dev ID {cid}"
    assert run.get("held_out_ids_consumed") == 0
    # Provenance: optimizer config + artifact hash present.
    assert run.get("optimizer") == "dspy.BootstrapFewShot"
    assert run.get("output_program_sha256")
