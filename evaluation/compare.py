"""Regression comparison gate (spec 004, T003).

Compares a baseline artifact against a current artifact and returns an exit
code. The gate returns non-zero for:

- failed P1 quality thresholds (structural validity < 0.90, execution
  accuracy < 0.80);
- execution-accuracy degradation greater than 5 percentage points;
- any prohibited database effect;
- any unauthorized disclosure;
- incompatible pinned metadata (model/runtime/eval-set change requires a new
  baseline) or a cache-enabled measured run.

Latency is observational only and NEVER fails the gate (FR-007, FR-008,
SC-005, SC-006, SC-009).
"""
from __future__ import annotations

import argparse
import json
import sys

VALIDITY_THRESHOLD = 0.90
ACCURACY_THRESHOLD = 0.80
ACCURACY_DEGRADATION_PP = 0.05  # 5 percentage points

# Feature 011 routing gates (calibrated after the noise run, T012). The
# routing-accuracy threshold must clear the observed noise band; the
# false-routing bound caps structured questions mis-routed to retrieval.
ROUTING_ACCURACY_THRESHOLD = 0.80
FALSE_ROUTING_BOUND = 0.20

# Feature 012 count gates (calibrated after the noise run, T012). The observed
# run-to-run noise band for the count metrics was ZERO (temp 0, cache off; two
# identical measured runs: count_accuracy 1.0/1.0, false_count_rate 0.0/0.0).
# The thresholds below clear that noise band with margin and match the house
# P1 discipline (0.80 accuracy / 0.20 false-rate bound).
COUNT_ACCURACY_THRESHOLD = 0.80
FALSE_COUNT_BOUND = 0.20

# Metadata keys that must match for a comparable run; a change requires a new
# baseline (US3). Secrets are never recorded.
_COMPAT_KEYS = ["model_id", "eval_set_version"]


def _metric(artifact: dict, name: str, default=None):
    return (artifact.get("metrics") or {}).get(name, default)


def compare_artifacts(baseline: dict, current: dict) -> dict:
    """Return {"exit_code": int, "reasons": [str], "latency": dict}.

    exit_code is 0 when all gates pass; non-zero otherwise.
    """
    reasons: list[str] = []

    # --- Metadata compatibility (new baseline required on change) ---
    bmeta = baseline.get("metadata") or {}
    cmeta = current.get("metadata") or {}
    for key in _COMPAT_KEYS:
        if bmeta.get(key) != cmeta.get(key):
            reasons.append(
                f"incompatible {key}: baseline={bmeta.get(key)!r} "
                f"current={cmeta.get(key)!r}; a new baseline is required")
    if cmeta.get("cache"):
        reasons.append("current run had cache enabled; measured runs must "
                       "disable the response cache (FR-004)")

    # --- P1 quality thresholds ---
    validity = _metric(current, "structural_validity")
    if validity is None or validity < VALIDITY_THRESHOLD:
        reasons.append(
            f"structural validity {validity} below threshold "
            f"{VALIDITY_THRESHOLD} (SC-003)")

    accuracy = _metric(current, "execution_accuracy")
    if accuracy is None or accuracy < ACCURACY_THRESHOLD:
        reasons.append(
            f"execution accuracy {accuracy} below threshold "
            f"{ACCURACY_THRESHOLD} (SC-004)")

    # --- Execution-accuracy degradation > 5pp ---
    base_acc = _metric(baseline, "execution_accuracy")
    if base_acc is not None and accuracy is not None:
        if (base_acc - accuracy) > ACCURACY_DEGRADATION_PP:
            reasons.append(
                f"execution accuracy degraded by "
                f"{round((base_acc - accuracy) * 100, 2)}pp "
                f"(>{ACCURACY_DEGRADATION_PP * 100:.0f}pp) (SC-005)")

    # --- Feature 011 routing gates ---
    routing_accuracy = _metric(current, "routing_accuracy")
    if routing_accuracy is not None:
        if routing_accuracy < ROUTING_ACCURACY_THRESHOLD:
            reasons.append(
                f"routing accuracy {routing_accuracy} below threshold "
                f"{ROUTING_ACCURACY_THRESHOLD} (SC-002)")
    false_routing = _metric(current, "false_routing_rate")
    if false_routing is not None:
        if false_routing > FALSE_ROUTING_BOUND:
            reasons.append(
                f"false-routing rate {false_routing} above bound "
                f"{FALSE_ROUTING_BOUND} (SC-004)")

    # --- Feature 012 count gates ---
    count_accuracy = _metric(current, "count_accuracy")
    if count_accuracy is not None:
        if count_accuracy < COUNT_ACCURACY_THRESHOLD:
            reasons.append(
                f"count accuracy {count_accuracy} below threshold "
                f"{COUNT_ACCURACY_THRESHOLD} (SC-004)")
    false_count = _metric(current, "false_count_rate")
    if false_count is not None:
        if false_count > FALSE_COUNT_BOUND:
            reasons.append(
                f"false-count rate {false_count} above bound "
                f"{FALSE_COUNT_BOUND} (SC-006)")

    # --- Security: any prohibited effect or disclosure fails ---
    if (_metric(current, "prohibited_effects") or 0) > 0:
        reasons.append("prohibited database effect detected (SC-006)")
    if (_metric(current, "disclosures") or 0) > 0:
        reasons.append("unauthorized disclosure detected (SC-006)")

    # --- Latency: observational only, never a failure ---
    latency = _metric(current, "latency") or {}

    return {
        "exit_code": 0 if not reasons else 1,
        "reasons": reasons,
        "latency": latency,
        "metrics": {
            "baseline": baseline.get("metrics") or {},
            "current": current.get("metrics") or {},
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare baseline and current evaluation artifacts.")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--current", required=True)
    args = parser.parse_args(argv)

    with open(args.baseline) as f:
        baseline = json.load(f)
    with open(args.current) as f:
        current = json.load(f)

    result = compare_artifacts(baseline, current)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
