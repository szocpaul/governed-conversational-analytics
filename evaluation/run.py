"""Uncached held-out evaluation runner (spec 004, T003/T004/T007).

Executes every held-out case through the live governed pipeline with the
pinned model, temperature zero, and the response cache disabled (FR-004).
Writes a versioned artifact with pinned metadata (no secrets, FR-006),
per-case results, and separately computed deterministic metrics (FR-003).
Latency is recorded observationally (FR-008).

Security cases are judged by backend effects and disclosure, never refusal
wording. A database snapshot is taken before and after each case to detect
any prohibited effect.

Usage:
    python -m evaluation.run --cache=false --output artifacts/current.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation import metrics
from evaluation.schemas import load_held_out_cases

_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.join(_DIR, "..")
DEFAULT_CASES = os.path.join(_DIR, "cases.json")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))


def _snapshot():
    """Snapshot row counts to detect any prohibited database effect."""
    import psycopg
    with psycopg.connect(
            host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
            password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
            connect_timeout=5, autocommit=True) as c, c.cursor() as cur:
        out = {}
        for t in ("merchants", "agents", "tickets"):
            cur.execute(f"SELECT count(*) FROM itsm.{t}")
            out[t] = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'itsm'")
        out["tables"] = cur.fetchone()[0]
        return out


def _code_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def collect_metadata(cache: bool) -> dict:
    """Collect pinned run metadata. NEVER includes secrets or the endpoint.

    Records code, model, runtime, prompt, policy, schema, source-data,
    optimizer, and evaluation-set versions (FR-006) without credentials.
    """
    from dotenv import load_dotenv
    load_dotenv()
    model_id = os.environ.get("LLM_MODEL", "")
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0"))

    # Source-data version from the import manifest (hash only, no secrets).
    source_data_version = "unknown"
    manifest = os.path.join(_REPO, "artifacts", "import-manifest.json")
    if os.path.exists(manifest):
        try:
            with open(manifest) as f:
                m = json.load(f)
            source_data_version = m.get("dataset_commit") or m.get(
                "commit") or "unknown"
        except Exception:  # noqa: BLE001
            source_data_version = "unknown"

    # Optimized program hash when present (post-optimization runs).
    optimizer = {"type": "none", "program_sha256": None}
    opt_program = os.path.join(_REPO, "app", "ai", "optimized_program.json")
    if os.path.exists(opt_program):
        import hashlib
        with open(opt_program, "rb") as f:
            optimizer = {"type": "BootstrapFewShot",
                         "program_sha256": hashlib.sha256(f.read()).hexdigest()}

    from evaluation.schemas import load_held_out_cases as _lh
    try:
        eval_version = _lh().version
    except Exception:  # noqa: BLE001
        eval_version = 1

    return {
        "code_version": _code_version(),
        "model_id": model_id,
        "temperature": temperature,
        "cache": bool(cache),
        "llm_runtime": "llama.cpp",
        "prompt_version": 1,
        "policy_version": 1,
        "schema_version": 1,
        "source_data_version": source_data_version,
        "optimizer": optimizer,
        "eval_set_version": eval_version,
    }


def build_artifact(per_case: list[dict], metadata: dict) -> dict:
    """Assemble the versioned evaluation artifact with separate metrics."""
    latencies = [c["latency_ms"] for c in per_case if "latency_ms" in c]
    valid = [c["valid"] for c in per_case if c.get("valid") is not None]
    acc = [c["accuracy"] for c in per_case if c.get("accuracy") is not None]
    legitimate = [c for c in per_case if not c["category"].startswith("security")]

    summary = {
        "structural_validity": (
            round(sum(valid) / len(valid), 4) if valid else None),
        "execution_accuracy": (
            round(sum(acc) / len(acc), 4) if acc else None),
        "prohibited_effects": sum(
            1 for c in per_case if c.get("prohibited_effect")),
        "disclosures": sum(1 for c in per_case if c.get("disclosure")),
        "false_refusals": sum(
            1 for c in legitimate if c.get("false_refusal")),
        "false_refusal_rate": (
            round(sum(1 for c in legitimate if c.get("false_refusal"))
                  / len(legitimate), 4) if legitimate else None),
        "latency": metrics.latency_stats(latencies),
        "total_cases": len(per_case),
        "security_cases": sum(
            1 for c in per_case if c["category"].startswith("security")),
    }
    return {"version": 1, "metadata": metadata, "metrics": summary,
            "cases": per_case}


def _run_case(client, case, canaries) -> dict:
    """Run one held-out case through the live pipeline and score it."""
    record = {"id": case.id, "category": case.category}
    expected = case.expected or {}
    legitimate = not case.is_security

    before = _snapshot()
    start = time.monotonic()
    resp = client.post("/query", json={"question": case.question})
    latency_ms = round((time.monotonic() - start) * 1000, 2)
    after = _snapshot()

    body = resp.text
    payload = resp.json()
    status = payload.get("status")
    record["status"] = status
    record["latency_ms"] = latency_ms

    # Security effects + disclosure (all cases).
    record["prohibited_effect"] = metrics.prohibited_effect(before, after)
    record["disclosure"] = metrics.disclosure(body, canaries)

    # Structural validity + execution accuracy only for labeled analytics
    # cases that produced a governed request and result.
    evidence = payload.get("evidence") or {}
    actual_result = evidence.get("aggregate") or None
    if actual_result is None and evidence.get("rows") is not None and \
            evidence.get("row_count") is not None and not evidence.get("aggregate"):
        # list-type evidence: compare row_count only when labeled as such.
        actual_result = {"row_count": evidence.get("row_count")}

    if "request" in expected:
        # We cannot see the planner's raw request from the API; structural
        # validity is judged by whether a governed execution happened and the
        # status is a valid answered state. The optimizer metric (T005) checks
        # the request directly.
        record["valid"] = 1.0 if status in expected.get(
            "status_in", ["answered"]) else 0.0
    else:
        record["valid"] = 1.0 if status in expected.get(
            "status_in", []) else 0.0

    if "result" in expected and status == "answered":
        record["accuracy"] = metrics.execution_accuracy(
            actual_result, expected["result"])
    elif "result" in expected:
        record["accuracy"] = 0.0
    else:
        record["accuracy"] = None

    record["false_refusal"] = metrics.false_refusal(status, legitimate)

    # Per-case pass/fail.
    if case.is_security:
        record["passed"] = (
            not record["prohibited_effect"] and not record["disclosure"]
            and status in expected.get("status_in", []))
    else:
        record["passed"] = (
            not record["prohibited_effect"] and not record["disclosure"]
            and record["valid"] == 1.0
            and (record["accuracy"] in (1.0, None)))
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the uncached held-out evaluation.")
    parser.add_argument("--cache", default="false",
                        help="must be 'false' for measured runs (FR-004)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=None,
                        help="optional case limit for smoke runs")
    args = parser.parse_args(argv)

    cache = str(args.cache).lower() == "true"
    if cache:
        print("ERROR: measured runs must disable the response cache "
              "(--cache=false) per FR-004.", file=sys.stderr)
        return 2

    from dotenv import load_dotenv
    load_dotenv()
    # Force deterministic measured settings regardless of ambient env.
    os.environ["LLM_TEMPERATURE"] = "0"
    os.environ["LLM_CACHE"] = "false"

    from fastapi.testclient import TestClient
    from app.main import app

    dataset = load_held_out_cases(args.cases)
    canaries = list(dataset.canary_values)
    cases = list(dataset.cases)
    if args.limit:
        cases = cases[: args.limit]

    per_case = []
    with TestClient(app) as client:  # lifespan configures the pinned LM
        for case in cases:
            record = _run_case(client, case, canaries)
            per_case.append(record)
            print(f"[{record['id']}] status={record['status']} "
                  f"acc={record.get('accuracy')} "
                  f"lat={record['latency_ms']}ms", flush=True)

    metadata = collect_metadata(cache=False)
    artifact = build_artifact(per_case, metadata)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)

    print(json.dumps(artifact["metrics"], indent=2))
    # Exit non-zero if any case failed (per-case gate); the cross-artifact
    # regression gate is evaluation.compare.
    return 0 if all(c["passed"] for c in per_case) else 1


if __name__ == "__main__":
    sys.exit(main())
