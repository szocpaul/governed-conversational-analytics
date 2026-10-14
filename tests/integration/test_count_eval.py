"""T015: Deterministic count-evaluation isolation checks (feature 012).

These tests are DETERMINISTIC (no live model, no stack): they verify the count
case files are physically separate with disjoint IDs, the leakage guard rejects
any held-out ID in a calibration trainset, the count-accuracy metric returns
correct values on canary cases, and the committed count-threshold.json records
only development case IDs and a valid threshold. (The live calibration and
held-out eval are quickstart procedures, not pytest.)
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest

from app.ai import count_calibration as calib
from app.ai import optimization as opt
from evaluation import metrics
from evaluation.schemas import load_dev_cases, load_held_out_cases

_REPO = os.path.join(os.path.dirname(__file__), "..", "..")
_THRESHOLD = os.path.join(_REPO, "count-threshold.json")


# ---------------------------------------------------------------------------
# 1. Physical separation + disjoint IDs
# ---------------------------------------------------------------------------

def test_count_case_files_physically_separate_and_disjoint():
    dev = load_dev_cases()
    held = load_held_out_cases()
    dev_ids = set(dev.ids)
    held_ids = set(held.ids)
    # Disjoint across the two files (no ID appears in both).
    assert not (dev_ids & held_ids), "dev/held-out case IDs must be disjoint"
    # The count cases exist in both files with the expected counts.
    dev_count = [c for c in dev.cases if c.category == "count_content"]
    held_count = [c for c in held.cases if c.category == "count_content"]
    assert len(dev_count) >= 5, "expected >= 5 development count cases"
    assert len(held_count) >= 5, "expected >= 5 held-out count cases"
    # A security count case exists in the held-out set.
    assert any(c.category.startswith("security") and "count" in c.category
               for c in held.cases), "expected a security count case"


def test_count_cases_have_labeled_counts():
    for c in load_dev_cases().cases:
        if c.category == "count_content":
            assert isinstance(c.expected.get("count"), int)
    for c in load_held_out_cases().cases:
        if c.category == "count_content":
            assert isinstance(c.expected.get("count"), int)


# ---------------------------------------------------------------------------
# 2. Leakage guard rejects held-out IDs in a calibration trainset
# ---------------------------------------------------------------------------

def test_calibration_dev_cases_are_dev_only():
    cases = calib._dev_count_cases()
    held_ids = set(load_held_out_cases().ids)
    assert cases, "expected development count cases"
    for c in cases:
        assert c.id not in held_ids
        assert c.id.startswith("DEV-")


def test_leakage_guard_rejects_held_out_id_in_calibration():
    held_ids = list(load_held_out_cases().ids)
    with pytest.raises(AssertionError):
        opt.assert_no_held_out_leakage(held_ids[:1])


def test_routing_trainset_includes_count_cases_dev_only():
    trainset = opt.build_routing_trainset()
    held_ids = set(load_held_out_cases().ids)
    routes = [e.expected_route for e in trainset]
    # The count cases contribute a content_count routing label.
    assert "content_count" in routes
    for e in trainset:
        assert e.case_id not in held_ids


# ---------------------------------------------------------------------------
# 3. Count-accuracy metric canary cases (1.0 / 0.0)
# ---------------------------------------------------------------------------

def test_count_correct_canary():
    assert metrics.count_correct(156, 156) == 1.0
    assert metrics.count_correct(156, 155) == 0.0
    assert metrics.count_correct(None, 5) == 0.0
    assert metrics.count_correct(5, None) == 0.0
    assert metrics.count_correct(True, 1) == 0.0  # bool rejected


def test_count_accuracy_aggregate():
    per_case = [{"count_correct": 1.0}, {"count_correct": 0.0},
                {"count_correct": 1.0}]
    assert metrics.count_accuracy(per_case) == round(2 / 3, 4)
    assert metrics.count_accuracy([]) is None


def test_false_count_rate_canary():
    per_case = [
        # content_count mis-routed to structured (a false-count).
        {"expected_route": "content_count", "predicted_category": "supported"},
        # content_count correctly routed.
        {"expected_route": "content_count", "predicted_category": "content_count"},
        # structured mis-routed to content_count (a false-count).
        {"expected_route": "supported", "predicted_category": "content_count"},
        # structured correctly routed.
        {"expected_route": "supported", "predicted_category": "supported"},
    ]
    assert metrics.false_count_rate(per_case) == 0.5
    assert metrics.false_count_rate([]) is None


# ---------------------------------------------------------------------------
# 4. Committed count-threshold.json records only dev IDs + a valid threshold
# ---------------------------------------------------------------------------

def test_count_threshold_artifact_valid_and_dev_only():
    assert os.path.exists(_THRESHOLD), "count-threshold.json must exist"
    with open(_THRESHOLD) as f:
        data = json.load(f)
    # A valid threshold (a real cosine-distance number, never hardcoded default).
    threshold = data.get("threshold")
    assert isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
    assert 0.0 < threshold < 1.0
    # Provenance: method + dev IDs + created_at + sha256.
    assert data.get("calibration_method")
    assert data.get("created_at")
    assert data.get("artifact_sha256")
    dev_ids = set(load_dev_cases().ids)
    held_ids = set(load_held_out_cases().ids)
    calib_ids = data.get("calibration_dev_ids") or []
    assert calib_ids, "calibration dev IDs must be recorded"
    for cid in calib_ids:
        assert cid in dev_ids, f"calibration ID {cid} is not a dev case"
        assert cid not in held_ids, f"calibration consumed held-out ID {cid}"


def test_count_threshold_artifact_sha256_matches():
    """The recorded artifact_sha256 equals the canonical-form hash (T017)."""
    with open(_THRESHOLD) as f:
        data = json.load(f)
    body = {k: v for k, v in data.items() if k != "artifact_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode()).hexdigest() == data["artifact_sha256"]
