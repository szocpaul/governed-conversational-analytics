# Quickstart Validation: Classifier-Based Content Routing

**Feature**: 011-classifier-content-routing | **Date**: 2026-10-14

Runnable end-to-end validation for the feature. Contracts referenced:
[classifier-signature](contracts/classifier-signature.md),
[routing-integration](contracts/routing-integration.md),
[evaluation](contracts/evaluation.md).

## Prerequisites

1. Stack healthy: `docker compose up -d` (PostgreSQL pgvector/pgvector:pg16,
   GraphJin 3.21.6), `.env` configured with the pinned chat AND embedding
   endpoint values.
2. Feature 010 complete: the embedding artifact is imported and governed
   retrieval works (verified per specs/010-hybrid-search/quickstart.md).
3. The +8 dev and +10 held-out routing cases are present in
   `evaluation/dev_cases.json` and `evaluation/cases.json`.

## Step 1 — Noise calibration (threshold setting)

Run the held-out evaluation on the CURRENT (pre-tuning) program 2-3 times at
temperature 0 and record the routing-relevant noise band:

```bash
python -m evaluation.run --cache=false --output /tmp/eval_cal_1.json
python -m evaluation.run --cache=false --output /tmp/eval_cal_2.json
```

Expected: the observed run-to-run variance is recorded; the routing-accuracy
and false-routing thresholds are set ABOVE the noise band and recorded in the
plan/runner notes.

## Step 2 — BootstrapFewShot tuning (dev-only)

```bash
python -m app.ai.optimization   # or the documented tuning entry point
```

Expected: the run consumes ONLY development routing cases (the leakage guard
passes), produces a tuned `app/ai/optimized_program.json` with routing demos,
and records provenance in `artifacts/optimization-run.json` (optimizer config,
accepted demo IDs, artifact hash, versions).

## Step 3 — Routing smoke test (live)

Through the conversational query path (`POST /query`):

- "Which tickets describe customers unable to complete a purchase because
  their card was rejected?" -> routed to retrieval, returns Card Declines
  tickets.
- "show me cases where people get locked out and can't prove who they are at
  sign-in" -> routed to retrieval, returns Account Access tickets.
- "tickets similar to 847207" -> routed to retrieval (similar mode), returns
  same-category tickets.
- "how many tickets about login" -> routed to the STRUCTURED path (a count),
  NOT retrieval.
- "how many P1 tickets are there?" -> structured path, unchanged.

Expected: deep paraphrases reach retrieval; structured questions stay on the
structured path; the trace shows the routing category.

## Step 4 — Held-out evaluation + comparison

```bash
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

Expected: routing accuracy >= calibrated threshold; false-routing rate <=
calibrated bound; the structured execution-accuracy gate does NOT regress;
security content cases return nothing prohibited; zero held-out IDs in the
tuning input. If routing accuracy does NOT reach the threshold: STOP AND
REPORT to the human (no degraded router, no GEPA/MIPROv2/SIMBA).

## Step 5 — Full regression

```bash
pytest -q
```

Expected: all 571 pre-existing tests pass plus the new unit/integration tests
of this feature; no failures introduced.

## Done criteria mapping

Step 1 -> SC-002/SC-004 (thresholds); Step 2 -> SC-005/SC-006 (tuning
discipline); Step 3 -> SC-001 (deep paraphrase routing) + SC-003 (structured
unchanged); Step 4 -> SC-002/SC-003/SC-004/SC-005/SC-007; Step 5 -> SC-008.
