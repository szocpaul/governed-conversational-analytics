"""Cross-version quality report (feature 006, T016; spec US5, FR-009).

Compares a preserved pre-upgrade result artifact (DSPy 3.2.1) with a new
post-upgrade artifact (DSPy 3.4.0) across validity, accuracy, security
metrics, false refusals, and observational latency, plus artifact SHA-256
hashes and runtime metadata.

This report is HUMAN DECISION INPUT for the manual gate. It is never gated
and produces NO pass/fail verdict (research.md D6: the same-version gate in
`evaluation/compare.py` keeps its clean hard-exit semantics; a regression
here is a human decision point, not an automatic rollback).

Usage:
    python3 -m evaluation.cross_version_report \
        --pre artifacts/current-pre-006-YYYY-MM-DD.json --pre-label 3.2.1 \
        --new artifacts/current.json --new-label 3.4.0 \
        --output artifacts/cross-version-006.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _section(artifact: dict, path: str, label: str) -> dict:
    """Build one version's report section from a result artifact."""
    metrics = artifact.get("metrics", {})
    metadata = artifact.get("metadata", {})
    cases = artifact.get("cases", [])
    per_request = [c["latency_ms"] for c in cases if "latency_ms" in c]
    latency = metrics.get("latency", {})
    return {
        "artifact": os.path.basename(path),
        "artifact_sha256": _sha256(path),
        # Preserved pre-upgrade artifacts predate the dspy_version metadata
        # field; fall back to the supplied version label.
        "dspy_version": metadata.get("dspy_version") or label,
        "python_version": metadata.get("python_version"),
        "model_id": metadata.get("model_id"),
        "temperature": metadata.get("temperature"),
        "cache": metadata.get("cache"),
        "structural_validity": metrics.get("structural_validity"),
        "execution_accuracy": metrics.get("execution_accuracy"),
        "prohibited_effects": metrics.get("prohibited_effects"),
        "disclosures": metrics.get("disclosures"),
        "false_refusals": metrics.get("false_refusals"),
        "false_refusal_rate": metrics.get("false_refusal_rate"),
        "total_cases": metrics.get("total_cases"),
        "security_cases": metrics.get("security_cases"),
        "latency": {
            "per_request_ms": per_request,
            "median": latency.get("median"),
            "p90": latency.get("p90"),
            "min": latency.get("min"),
            "max": latency.get("max"),
        },
    }


def build_report(pre_path: str, new_path: str,
                 pre_label: str, new_label: str) -> dict:
    """Assemble the cross-version report. Never emits a pass/fail verdict."""
    with open(pre_path) as f:
        pre = json.load(f)
    with open(new_path) as f:
        new = json.load(f)
    return {
        "report": "cross-version quality comparison (human review input; "
                  "not gated)",
        "versions": {
            pre_label: _section(pre, pre_path, pre_label),
            new_label: _section(new, new_path, new_label),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-version quality report (never gated).")
    parser.add_argument("--pre", required=True,
                        help="preserved pre-upgrade result artifact")
    parser.add_argument("--pre-label", required=True)
    parser.add_argument("--new", required=True,
                        help="new post-upgrade result artifact")
    parser.add_argument("--new-label", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    report = build_report(args.pre, args.new, args.pre_label, args.new_label)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Cross-version report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
