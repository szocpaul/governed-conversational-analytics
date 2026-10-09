"""BootstrapFewShot optimization isolated to development cases (spec 004, T005/T006).

The ONLY approved optimizer is dspy.BootstrapFewShot with a bounded
configuration. Optimization consumes ONLY development case IDs; held-out IDs
are guarded against leakage (FR-009, SC-007). The binary metric returns 1.0
only when every mandatory check passes; otherwise 0.0 (no partial credit).

GEPA, MIPROv2, SIMBA, and fine-tuning are prohibited here.
"""
from __future__ import annotations

import hashlib
import json
import os

import dspy

from evaluation import metrics
from evaluation.schemas import load_dev_cases, load_held_out_cases

_REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OPTIMIZED_PROGRAM_PATH = os.path.join(
    _REPO, "app", "ai", "optimized_program.json")
OPTIMIZATION_RUN_PATH = os.path.join(
    _REPO, "artifacts", "optimization-run.json")

MIN_DEV_EXAMPLES = 12


# ---------------------------------------------------------------------------
# Optimizer configuration (bounded, approved)
# ---------------------------------------------------------------------------

def optimizer_config() -> dict:
    """Return the approved bounded BootstrapFewShot configuration."""
    return {
        "metric_threshold": 1.0,
        "max_bootstrapped_demos": 4,
        "max_labeled_demos": 4,
        "max_rounds": 1,
        "max_errors": 3,
    }


# ---------------------------------------------------------------------------
# Isolation guards (SC-007)
# ---------------------------------------------------------------------------

def assert_no_held_out_leakage(case_ids) -> None:
    """Raise AssertionError if any held-out ID is present."""
    held_ids = set(load_held_out_cases().ids)
    leaked = [cid for cid in case_ids if cid in held_ids]
    if leaked:
        raise AssertionError(
            f"held-out case IDs leaked into optimization: {leaked}")


def build_trainset(extra_cases=None) -> list[dspy.Example]:
    """Build the optimization trainset from development cases ONLY.

    Each example carries the labeled governed request and normalized expected
    result. Any non-development (held-out) case raises ValueError (SC-007).
    """
    dev = load_dev_cases()
    held_ids = set(load_held_out_cases().ids)

    cases = list(dev.cases)
    if extra_cases:
        for c in extra_cases:
            if c.id in held_ids:
                raise ValueError(
                    f"held-out case {c.id!r} must not enter optimization")
            cases.append(c)

    trainset = []
    for c in cases:
        if c.id in held_ids:
            raise ValueError(
                f"held-out case {c.id!r} must not enter optimization")
        expected = c.expected or {}
        # Only supported analytics cases with a labeled request are usable
        # for bootstrap demonstrations.
        if "request" not in expected or "result" not in expected:
            continue
        ex = dspy.Example(
            case_id=c.id,
            question=c.question,
            expected_request=expected["request"],
            expected_result=expected["result"],
        ).with_inputs("question")
        trainset.append(ex)

    assert_no_held_out_leakage([e.case_id for e in trainset])
    return trainset


# ---------------------------------------------------------------------------
# Binary optimizer metric
# ---------------------------------------------------------------------------

def text_to_query_metric(example, pred, trace=None) -> float:
    """Return 1.0 only when every mandatory check passes; else 0.0.

    Mandatory checks:
      - structured output validates against the governed schema;
      - the request is read-only and policy-allowed;
      - governed execution succeeded (pred.executed with a result);
      - the normalized execution result matches the labeled expected result;
      - no prohibited effect or unauthorized disclosure occurred.
    """
    request = getattr(pred, "request", None)
    executed = getattr(pred, "executed", False)
    execution_result = getattr(pred, "execution_result", None)
    prohibited = getattr(pred, "prohibited_effect", False)
    disclosed = getattr(pred, "disclosure", False)

    # Security: any prohibited effect or disclosure fails immediately.
    if prohibited or disclosed:
        return 0.0

    # Structured output must exist and validate.
    if request is None:
        return 0.0
    if metrics.structural_validity(request) != 1.0:
        return 0.0

    # Request must be read-only and policy-allowed.
    if not metrics.is_read_only(request):
        return 0.0

    # Governed execution must have succeeded with a result.
    if not executed or execution_result is None:
        return 0.0

    # Normalized result must match the labeled expected result.
    if metrics.execution_accuracy(execution_result,
                                  example.expected_result) != 1.0:
        return 0.0

    return 1.0


# ---------------------------------------------------------------------------
# Compilation (T006)
# ---------------------------------------------------------------------------

def compile_program(program=None, trainset=None):
    """Compile the query program with BootstrapFewShot on development cases.

    Returns (optimized_program, run_metadata). Raises RuntimeError when fewer
    than MIN_DEV_EXAMPLES valid labeled development examples exist (the caller
    must then record the unoptimized baseline and skip optimization).
    """
    if trainset is None:
        trainset = build_trainset()
    if len(trainset) < MIN_DEV_EXAMPLES:
        raise RuntimeError(
            f"only {len(trainset)} valid labeled development examples; "
            f"need >= {MIN_DEV_EXAMPLES}. Record the unoptimized baseline "
            f"and skip optimization (no held-out substitution).")

    if program is None:
        from app.ai.query_program import QueryProgram
        program = QueryProgram()

    cfg = optimizer_config()
    optimizer = dspy.BootstrapFewShot(
        metric=text_to_query_metric,
        metric_threshold=cfg["metric_threshold"],
        max_bootstrapped_demos=cfg["max_bootstrapped_demos"],
        max_labeled_demos=cfg["max_labeled_demos"],
        max_rounds=cfg["max_rounds"],
        max_errors=cfg["max_errors"],
    )
    optimized = optimizer.compile(program, trainset=trainset)

    consumed_ids = [e.case_id for e in trainset]
    assert_no_held_out_leakage(consumed_ids)

    return optimized, {
        "optimizer": "dspy.BootstrapFewShot",
        "config": cfg,
        "input_case_ids": consumed_ids,
        "trainset_size": len(trainset),
    }
