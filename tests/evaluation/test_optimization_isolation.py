"""Optimization isolation tests (spec 004, T005, SC-007).

Written BEFORE app/ai/optimization.py. Prove that optimization consumes ONLY
development case IDs and that zero held-out IDs ever enter the optimizer.
"""
from __future__ import annotations

import pytest

from app.ai import optimization
from evaluation.schemas import load_dev_cases, load_held_out_cases


def test_dev_and_held_out_ids_are_disjoint():
    dev = load_dev_cases()
    held = load_held_out_cases()
    assert set(dev.ids).isdisjoint(set(held.ids))


def test_build_trainset_uses_only_dev_ids():
    trainset = optimization.build_trainset()
    dev_ids = set(load_dev_cases().ids)
    held_ids = set(load_held_out_cases().ids)
    assert len(trainset) >= 1
    for ex in trainset:
        assert ex.case_id in dev_ids
        assert ex.case_id not in held_ids


def test_build_trainset_rejects_held_out_injection():
    """Guard: a held-out case passed to the trainset builder is rejected."""
    held = load_held_out_cases()
    held_case = held.cases[0]
    with pytest.raises(ValueError):
        optimization.build_trainset(extra_cases=[held_case])


def test_assert_no_held_out_leakage_detects_leak():
    held_ids = set(load_held_out_cases().ids)
    leaked = next(iter(held_ids))
    with pytest.raises(AssertionError):
        optimization.assert_no_held_out_leakage([leaked])


def test_assert_no_held_out_leakage_passes_for_dev():
    dev_ids = list(load_dev_cases().ids)
    # Should not raise.
    optimization.assert_no_held_out_leakage(dev_ids)


def test_optimizer_config_is_bounded():
    cfg = optimization.optimizer_config()
    assert cfg["metric_threshold"] == 1.0
    assert cfg["max_bootstrapped_demos"] == 4
    assert cfg["max_labeled_demos"] == 4
    assert cfg["max_rounds"] == 1
    assert cfg["max_errors"] == 3
