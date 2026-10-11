"""Cross-version report generator tests (feature 006, T015; spec US5, FR-009).

The report compares the preserved pre-upgrade (DSPy 3.2.1) results with the
new 3.4.0 results as human decision input. It covers validity, accuracy,
security metrics, false refusals, and latency for both versions, plus
artifact hashes and runtime metadata. It NEVER produces a pass/fail verdict
(the cross-version delta is a human review item, not a gate).
"""
from __future__ import annotations

import json

import pytest

from evaluation import cross_version_report as cvr


def _artifact(structural_validity=1.0, execution_accuracy=1.0,
              prohibited_effects=0, disclosures=0, false_refusals=0,
              latencies=None, dspy_version=None, python_version=None,
              model_id="m", total_cases=2, security_cases=0):
    latencies = latencies if latencies is not None else [100.0, 200.0]
    cases = [
        {"id": f"C{i}", "category": "count", "status": "answered",
         "latency_ms": lat, "prohibited_effect": False, "disclosure": False,
         "valid": structural_validity, "accuracy": execution_accuracy,
         "false_refusal": False, "passed": True}
        for i, lat in enumerate(latencies)
    ]
    metadata = {"model_id": model_id, "temperature": 0.0, "cache": False}
    if dspy_version is not None:
        metadata["dspy_version"] = dspy_version
    if python_version is not None:
        metadata["python_version"] = python_version
    return {
        "version": 1,
        "metadata": metadata,
        "metrics": {
            "structural_validity": structural_validity,
            "execution_accuracy": execution_accuracy,
            "prohibited_effects": prohibited_effects,
            "disclosures": disclosures,
            "false_refusals": false_refusals,
            "false_refusal_rate": false_refusals / max(total_cases, 1),
            "latency": {"count": len(latencies), "median": 150.0,
                        "p90": 190.0, "min": min(latencies),
                        "max": max(latencies)},
            "total_cases": total_cases,
            "security_cases": security_cases,
        },
        "cases": cases,
    }


def test_report_contains_per_version_metrics_and_no_verdict(tmp_path):
    pre = _artifact(dspy_version=None, python_version=None,
                    execution_accuracy=0.9, latencies=[100.0, 300.0])
    new = _artifact(dspy_version="3.4.0", python_version="3.14.4",
                    execution_accuracy=1.0, latencies=[120.0, 240.0])
    pre_path = tmp_path / "pre.json"
    new_path = tmp_path / "new.json"
    pre_path.write_text(json.dumps(pre))
    new_path.write_text(json.dumps(new))

    report = cvr.build_report(
        pre_path=str(pre_path), new_path=str(new_path),
        pre_label="3.2.1", new_label="3.4.0")

    # Per-version metric coverage.
    for version_key in ("3.2.1", "3.4.0"):
        section = report["versions"][version_key]
        for field in ("structural_validity", "execution_accuracy",
                      "prohibited_effects", "disclosures",
                      "false_refusals", "false_refusal_rate"):
            assert field in section, (version_key, field)
        lat = section["latency"]
        for field in ("per_request_ms", "median", "p90", "max"):
            assert field in lat, (version_key, field)
        assert lat["per_request_ms"], "per-request latency values required"

    # Accuracy values propagated.
    assert report["versions"]["3.2.1"]["execution_accuracy"] == 0.9
    assert report["versions"]["3.4.0"]["execution_accuracy"] == 1.0

    # Artifact hashes + runtime metadata.
    for version_key in ("3.2.1", "3.4.0"):
        assert report["versions"][version_key]["artifact_sha256"]
    assert report["versions"]["3.4.0"]["dspy_version"] == "3.4.0"
    assert report["versions"]["3.4.0"]["python_version"] == "3.14.4"
    assert report["versions"]["3.2.1"]["dspy_version"] == "3.2.1"  # from label

    # NO pass/fail verdict anywhere.
    blob = json.dumps(report).lower()
    for forbidden in ('"passed"', '"verdict"', '"gate"', '"fail"'):
        assert forbidden not in blob, forbidden


def test_report_missing_version_falls_back_to_label(tmp_path):
    # Preserved 3.2.1 artifacts predate the dspy_version metadata field.
    pre = _artifact()  # no dspy_version in metadata
    pre_path = tmp_path / "pre.json"
    pre_path.write_text(json.dumps(pre))
    report = cvr.build_report(
        pre_path=str(pre_path), new_path=str(pre_path),
        pre_label="3.2.1", new_label="3.4.0")
    assert report["versions"]["3.2.1"]["dspy_version"] == "3.2.1"
