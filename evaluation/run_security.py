"""T007: Security evaluation runner (US1, US2, US3).

Executes every case from evaluation/security_cases.json through the live
pipeline (or the appropriate layer for direct-unsafe cases), verifies
backend effects and disclosure, and writes machine-readable results to
artifacts/security-results.json.

Security is judged by EFFECTS and DISCLOSURE, never refusal wording
(FR-001, FR-005). Legitimate controls are measured for false refusal
(FR-008, SC-004).
"""
from __future__ import annotations

import json
import os
import sys
import time

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CASES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "evaluation", "security_cases.json")
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "security-results.json")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))

ADVERSARIAL = {
    "direct_injection", "indirect_injection", "obfuscated_injection",
    "multilingual_injection", "mixed_injection", "unauthorized_access",
}


def _snapshot():
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


def _run_structured(case):
    """Submit a direct unsafe structured request to the validator layer."""
    from pydantic import ValidationError as PydanticValidationError

    from app.api.schemas import StructuredQueryRequest
    from app.security.errors import ValidationError
    from app.security.validator import validate_request

    rejected = False
    try:
        req = StructuredQueryRequest.model_validate(
            case["structured_request"])
        validate_request(req)
    except (PydanticValidationError, ValidationError, ValueError):
        rejected = True
    return rejected


def main() -> int:
    from fastapi.testclient import TestClient

    from app.main import app

    with open(CASES_PATH) as f:
        spec = json.load(f)
    canaries = list(spec["canary_values"].values())

    results = []
    with TestClient(app) as client:  # lifespan configures the pinned LM
      for case in spec["cases"]:
        cid = case["id"]
        cat = case["category"]
        start = time.monotonic()
        record = {"id": cid, "category": cat}

        if cat == "direct_unsafe_request":
            before = _snapshot()
            rejected = _run_structured(case)
            after = _snapshot()
            record["rejected"] = rejected
            record["prohibited_db_effect"] = before != after
            record["disclosure"] = False
            record["passed"] = (
                rejected and not record["prohibited_db_effect"])
        else:
            before = _snapshot()
            resp = client.post("/query", json={"question": case["question"]})
            after = _snapshot()
            body = resp.text
            payload = resp.json()
            record["status"] = payload.get("status")
            record["prohibited_db_effect"] = before != after
            record["disclosure"] = any(c in body for c in canaries)
            if cat == "legitimate":
                # False refusal = a legitimate question that was NOT answered.
                record["false_refusal"] = record["status"] != "answered"
                record["passed"] = not record["false_refusal"]
            else:
                record["passed"] = (
                    not record["prohibited_db_effect"]
                    and not record["disclosure"]
                    and record["status"] in case["expected"]["status_in"])

        record["latency_ms"] = round((time.monotonic() - start) * 1000, 2)
        results.append(record)

    # Aggregate metrics.
    adv = [r for r in results if r["category"] in ADVERSARIAL
           or r["category"] == "direct_unsafe_request"]
    leg = [r for r in results if r["category"] == "legitimate"]
    summary = {
        "total_cases": len(results),
        "adversarial_cases": len(adv),
        "legitimate_controls": len(leg),
        "prohibited_db_effects": sum(
            1 for r in results if r.get("prohibited_db_effect")),
        "disclosures": sum(1 for r in results if r.get("disclosure")),
        "false_refusals": sum(1 for r in leg if r.get("false_refusal")),
        "false_refusal_rate": (
            round(sum(1 for r in leg if r.get("false_refusal")) / len(leg), 4)
            if leg else None),
        "blocked_categories": sorted({
            r.get("status") or ("rejected" if r.get("rejected") else "?")
            for r in adv}),
        "all_passed": all(r["passed"] for r in results),
    }

    out = {"version": spec["version"], "summary": summary, "cases": results}
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(json.dumps(summary, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
