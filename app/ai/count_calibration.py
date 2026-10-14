"""Deterministic semantic-threshold calibration for count over content (feature 012).

Contracts/evaluation.md + research R3: the semantic-match threshold is calibrated
by a DETERMINISTIC distance sweep over the DEVELOPMENT count cases only. For a
grid of candidate thresholds, each dev count question's topic is embedded (pinned
EmbeddingGemma-2) and the governed hybrid count is computed; the threshold that
maximizes exact-count accuracy on dev is chosen (ties broken toward the LARGER
threshold = more inclusive). The calibrated threshold is written to a versioned,
committed artifact (count-threshold.json) with provenance (calibration dev IDs,
method, created_at, artifact SHA-256).

This is a deterministic sweep, NOT a forbidden optimizer (no GEPA/MIPROv2/SIMBA/
fine-tuning). It consumes development cases ONLY; assert_no_held_out_leakage
guards it (zero held-out IDs).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from app.ai.retrieval import (
    CountThresholdError,
    build_count_query,
    _connect,
    _vector_literal,
)
from app.ai.routing import extract_count_topic
from evaluation.schemas import load_dev_cases, load_held_out_cases

_REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
COUNT_THRESHOLD_PATH = os.path.join(_REPO, "count-threshold.json")
THRESHOLD_VERSION = "1"
CALIBRATION_METHOD = "deterministic distance sweep over dev count cases"

# Candidate cosine-distance thresholds (the governed sweep grid). Chosen to
# bracket the stable region observed live (semantic adds genuine paraphrases
# around 0.20-0.30; larger values over-match).
DEFAULT_GRID = (0.18, 0.20, 0.22, 0.24, 0.25, 0.26, 0.28, 0.30, 0.32, 0.35)


def _dev_count_cases():
    """Return the development count-over-content cases (dev-only, guarded)."""
    dev = load_dev_cases()
    held_ids = set(load_held_out_cases().ids)
    out = []
    for c in dev.cases:
        if c.id in held_ids:
            raise ValueError(
                f"held-out case {c.id!r} must not enter calibration")
        if c.category != "count_content":
            continue
        expected = c.expected or {}
        if "count" not in expected:
            continue
        out.append(c)
    return out


def _embed(text: str) -> list[float]:
    """Embed the count topic with the pinned EmbeddingGemma-2 endpoint."""
    from app.ai.embeddings import EmbeddingConfig, EmbeddingProgram
    program = EmbeddingProgram(config=EmbeddingConfig.from_env())
    return program._embed_once(text)


def _hybrid_count(query_text: str, qvec: list[float], threshold: float) -> int:
    """Compute the governed hybrid count at a candidate threshold."""
    sql, params = build_count_query(query_text, qvec, threshold)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return int(cur.fetchone()[0])


def calibrate_threshold(grid=DEFAULT_GRID, *, embed_query=None,
                        count_fn=None) -> dict:
    """Run the deterministic sweep over dev count cases; return the result.

    For each candidate threshold, compute the hybrid count for every dev count
    case and score exact-count accuracy. Pick the threshold maximizing dev
    accuracy; ties break toward the LARGER threshold. Returns a provenance
    record (threshold, version, method, dev IDs, per-threshold accuracy).

    `embed_query` / `count_fn` are injectable for deterministic tests.
    """
    cases = _dev_count_cases()
    if not cases:
        raise CountThresholdError(
            "no development count_content cases available for calibration")
    dev_ids = [c.id for c in cases]

    # Isolation guard: zero held-out IDs (SC-007).
    from app.ai.optimization import assert_no_held_out_leakage
    assert_no_held_out_leakage(dev_ids)

    embed_query = embed_query or _embed
    count_fn = count_fn or _hybrid_count

    # Embed each dev topic once; reuse across the grid.
    topics = {}
    vectors = {}
    for c in cases:
        topic = extract_count_topic(c.question) or c.question
        topics[c.id] = topic
        vectors[c.id] = embed_query(topic)

    per_threshold: list[dict] = []
    best_threshold = None
    best_accuracy = -1.0
    for thr in grid:
        thr = float(thr)
        correct = 0
        for c in cases:
            expected = int(c.expected["count"])
            actual = count_fn(topics[c.id], vectors[c.id], thr)
            if actual == expected:
                correct += 1
        accuracy = correct / len(cases)
        per_threshold.append({"threshold": thr,
                              "exact_count_accuracy": round(accuracy, 4),
                              "correct": correct, "total": len(cases)})
        # Maximize accuracy; ties break toward the LARGER threshold.
        if accuracy > best_accuracy or (
                accuracy == best_accuracy and best_threshold is not None
                and thr > best_threshold):
            best_accuracy = accuracy
            best_threshold = thr

    return {
        "threshold": best_threshold,
        "dev_exact_count_accuracy": round(best_accuracy, 4),
        "calibration_dev_ids": dev_ids,
        "per_threshold": per_threshold,
    }


def _canonical_form(record: dict) -> str:
    """Canonical JSON (without artifact_sha256) for hashing."""
    body = {k: v for k, v in record.items() if k != "artifact_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def write_threshold_artifact(result: dict,
                             path: str = COUNT_THRESHOLD_PATH) -> dict:
    """Write the versioned threshold artifact with provenance + SHA-256.

    The artifact records the calibrated threshold, version, calibration method,
    the development case IDs used, created_at, and the SHA-256 of its canonical
    form. Never hand-edited; produced only by this calibration run.
    """
    record = {
        "threshold": float(result["threshold"]),
        "version": THRESHOLD_VERSION,
        "calibration_method": CALIBRATION_METHOD,
        "calibration_dev_ids": list(result["calibration_dev_ids"]),
        "dev_exact_count_accuracy": result["dev_exact_count_accuracy"],
        "per_threshold": result["per_threshold"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    record["artifact_sha256"] = hashlib.sha256(
        _canonical_form(record).encode()).hexdigest()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return record


def run_calibration(path: str = COUNT_THRESHOLD_PATH) -> int:
    """Calibrate the threshold on dev cases and write the artifact.

    Returns 0 on success, 1 on error. Consumes development cases ONLY.
    """
    from dotenv import load_dotenv
    load_dotenv()
    result = calibrate_threshold()
    record = write_threshold_artifact(result, path)
    print(json.dumps({
        "threshold": record["threshold"],
        "dev_exact_count_accuracy": record["dev_exact_count_accuracy"],
        "calibration_dev_ids": record["calibration_dev_ids"],
        "artifact_sha256": record["artifact_sha256"],
        "per_threshold": record["per_threshold"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_calibration())
