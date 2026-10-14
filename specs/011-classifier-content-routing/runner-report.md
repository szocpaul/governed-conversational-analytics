# Runner Report: Feature 011 — Classifier-Based Content Routing

**Feature**: 011-classifier-content-routing
**Date started**: 2026-10-14
**Status**: IN PROGRESS

This report follows the AGENTS.md Required Final Report structure. It is
completed incrementally as tasks finish (T018 finalizes it).

---

## Pre-implementation baseline (T001)

- **Git commit (start)**: `3dc60335337fbc182ba6af673bc59c06cdf31646`
  (short `3dc6033`, branch `main`)
- **Working-tree state at start**:
  - `M artifacts/import-manifest.json` — pre-existing benign timestamp-only
    refresh (`imported_at` fields) from a clean-reset import after the stack
    restart; NOT made by this runner and left untouched (do-not-overwrite).
  - `?? specs/011-classifier-content-routing-sketch.md` — feature sketch (input).
  - `?? specs/011-classifier-content-routing/` — this feature's spec artifacts.
- **Pre-existing test suite**: `pytest -q` -> **571 passed, 0 failed**
  (236.78s). Baseline green, as expected (SC-008 starting point).

## Endpoint preflight (T002)

- **Chat endpoint**: `GET /v1/models` -> 200; exact pinned model ID
  `models\Qwen3.8-27B-UD-Q4_K_M.gguf` PRESENT. Used for classification.
- **Embedding endpoint**: `GET /v1/models` -> 200; exact pinned model ID
  `models\embeddinggemma-2-Q8_0.gguf` PRESENT; live embedding probe returned
  dimension 768. Used for retrieval query embedding.
- **Stack**: `docker compose ps` -> PostgreSQL `pgvector/pgvector:pg16`
  (healthy), GraphJin `dosco/graphjin:3.21.6` (up); GraphQL probe -> 200.
- No fallback model, no hosted API. All pinned values match `.env`.

---

## Completed task IDs

(pending)

## Incomplete / blocked task IDs

(pending)

## Files changed

(pending)

## Commits created

(pending)

## Exact pinned dependency versions

(pending)

## Validation commands and results

(pending)

## Noise-calibration thresholds (T012)

(pending)

## Routing accuracy / false-routing / structured-regression (T014)

(pending)

## Security content-case results

(pending)

## Latency (observational only)

(pending)

## Known limitations

(pending)

## Outstanding manual gates

None for this feature (the stop-and-report on insufficient tuning is a human
decision point, not an agent-tickable MANUAL GATE).
