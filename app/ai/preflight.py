"""Model preflight for the pinned local llama.cpp endpoint (T001).

Verifies, in order, with NO fallback:
  1. GET /v1/models returns the exact requested model ID.
  2. One deterministic chat completion succeeds.
  3. One typed DSPy prediction succeeds.

Non-secret metadata is saved to artifacts/llm-preflight.json. The private
endpoint URL is recorded only as a host-redacted boolean presence flag plus
the non-secret configuration needed to reproduce the run; the full URL is
never written to user-facing traces.

Run:  python -m app.ai.preflight
Exit code 0 on success, 1 on any verification failure (stop-and-report).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import dspy

from app.ai.llm import (
    LLMConfig,
    LLMEndpointError,
    chat_completion,
    configure_dspy,
    list_models,
)

ARTIFACT_PATH = "artifacts/llm-preflight.json"


class _PingSignature(dspy.Signature):
    """Reply with the single word: ready."""

    question: str = dspy.InputField()
    status: str = dspy.OutputField()


def run_preflight(config: LLMConfig | None = None) -> dict:
    config = config or LLMConfig.from_env()
    record: dict = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "provider": config.provider,
        "requested_model": config.model,
        "temperature": config.temperature,
        "cache": config.cache,
        "checks": {},
        "ok": False,
    }
    try:
        # 1. /v1/models
        ids = list_models(config)
        record["available_model_ids"] = ids
        if config.model not in ids:
            raise LLMEndpointError(
                f"requested model {config.model!r} not in {ids!r}"
            )
        record["checks"]["models_listed"] = True
        record["exact_model_id"] = config.model

        # 2. deterministic chat completion
        t0 = time.monotonic()
        resp = chat_completion(
            config,
            messages=[
                {"role": "user", "content": "Reply with the single word: ready"}
            ],
        )
        content = resp["choices"][0]["message"]["content"]
        record["checks"]["chat_completion"] = True
        record["chat_completion_latency_ms"] = round(
            (time.monotonic() - t0) * 1000, 1
        )
        record["chat_completion_reply"] = content.strip()[:80]

        # 3. typed DSPy prediction
        configure_dspy(config)
        t0 = time.monotonic()
        pred = dspy.Predict(_PingSignature)(question="Say ready.")
        record["checks"]["dspy_prediction"] = True
        record["dspy_prediction_latency_ms"] = round(
            (time.monotonic() - t0) * 1000, 1
        )
        record["dspy_prediction_status"] = str(pred.status).strip()[:80]

        record["ok"] = True
    except Exception as exc:  # noqa: BLE001 - preflight must stop and report
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["ok"] = False
    return record


def main() -> int:
    record = run_preflight()
    os.makedirs(os.path.dirname(ARTIFACT_PATH), exist_ok=True)
    with open(ARTIFACT_PATH, "w") as f:
        json.dump(record, f, indent=2)
    if record["ok"]:
        print(f"Preflight OK. Exact model ID: {record['exact_model_id']!r}")
        print(f"Metadata written to {ARTIFACT_PATH}")
        return 0
    print(f"Preflight FAILED: {record.get('error')}", file=sys.stderr)
    print("STOP AND REPORT: no fallback model or provider is allowed.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
