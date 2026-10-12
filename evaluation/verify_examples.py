"""Live verification of the curated example gallery (spec 008, T008, SC-002).

Runs every gallery question from ``app/web/examples.json`` through the live
governed pipeline (the same FastAPI code path as ``evaluation/run.py``):

- every ``answerable`` question MUST return a grounded, non-clarification
  answer (status ``answered``);
- every ``refusal_demo`` question MUST be refused (status ``unsupported``
  with a ``refused`` trace event, and no executed query);
- no response may disclose prohibited content (private endpoint details or
  canary markers, FR-009).

Read-only: no database writes, no evaluation-corpus changes. Writes a
versioned artifact with per-question outcomes and pinned metadata, and
exits non-zero on any failure.

Usage:
    python -m evaluation.verify_examples --output artifacts/examples-verification.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.run import collect_metadata  # noqa: E402

_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.join(_DIR, "..")
EXAMPLES_PATH = os.path.join(_REPO, "app", "web", "examples.json")

# Disclosure probes (FR-009): private endpoint markers and canary prefixes
# must never appear in any user-facing response.
PROHIBITED_SUBSTRINGS = ("tailee6bc1", "8033", "CANARY")


def load_gallery(path: str = EXAMPLES_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def _verify_question(client, entry: dict) -> dict:
    """Run one gallery question live and judge its outcome."""
    record = {
        "question": entry["question"],
        "category": entry["category"],
        "outcome": entry["outcome"],
    }
    start = time.monotonic()
    resp = client.post("/query", json={"question": entry["question"]})
    record["latency_ms"] = round((time.monotonic() - start) * 1000, 2)
    body = resp.text
    payload = resp.json()
    status = payload.get("status")
    record["status"] = status

    record["disclosure"] = any(s in body for s in PROHIBITED_SUBSTRINGS)
    trace_events = {e.get("event") for e in (payload.get("trace") or [])}

    if entry["outcome"] == "answerable":
        # Grounded answer required: never a wording-caused clarification
        # (FR-003, SC-002). Evidence must be present and non-empty.
        evidence = payload.get("evidence") or {}
        has_evidence = bool(
            evidence.get("rows") or evidence.get("aggregate")
            or evidence.get("row_count"))
        record["passed"] = (
            status == "answered" and has_evidence
            and not record["disclosure"])
    else:  # refusal_demo
        # Intentional refusal: stable unsupported status, a "refused" trace
        # event, and no governed execution (FR-003 edge case).
        record["passed"] = (
            status == "unsupported"
            and "refused" in trace_events
            and "executed" not in trace_events
            and not record["disclosure"])
    return record


def build_artifact(records: list[dict], metadata: dict,
                   examples_sha256: str) -> dict:
    per_category = {}
    for r in records:
        bucket = per_category.setdefault(
            r["category"], {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += 1 if r["passed"] else 0
    summary = {
        "total_questions": len(records),
        "answerable": sum(1 for r in records if r["outcome"] == "answerable"),
        "refusal_demos": sum(
            1 for r in records if r["outcome"] == "refusal_demo"),
        "answered": sum(1 for r in records if r["status"] == "answered"),
        "refused": sum(
            1 for r in records
            if r["outcome"] == "refusal_demo" and r["status"] == "unsupported"),
        "clarifications": sum(
            1 for r in records if r["status"] == "clarification"),
        "disclosures": sum(1 for r in records if r["disclosure"]),
        "per_category": per_category,
        "all_passed": all(r["passed"] for r in records),
    }
    return {
        "version": 1,
        "kind": "examples_verification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "examples_sha256": examples_sha256,
        "metadata": metadata,
        "summary": summary,
        "results": records,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify every curated gallery question end-to-end "
                    "against the live governed pipeline (SC-002).")
    parser.add_argument("--output", required=True)
    parser.add_argument("--examples", default=EXAMPLES_PATH)
    args = parser.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv()
    # Deterministic measured settings, same discipline as evaluation.run.
    os.environ["LLM_TEMPERATURE"] = "0"
    os.environ["LLM_CACHE"] = "false"

    with open(args.examples, "rb") as f:
        examples_sha256 = hashlib.sha256(f.read()).hexdigest()
    gallery = load_gallery(args.examples)

    from fastapi.testclient import TestClient
    from app.main import app

    records = []
    with TestClient(app) as client:  # lifespan configures the pinned LM
        for entry in gallery["examples"]:
            record = _verify_question(client, entry)
            records.append(record)
            print(f"[{record['category']}] {record['question'][:60]} "
                  f"-> status={record['status']} "
                  f"passed={record['passed']} "
                  f"lat={record['latency_ms']}ms", flush=True)

    metadata = collect_metadata(cache=False)
    artifact = build_artifact(records, metadata, examples_sha256)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)

    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
