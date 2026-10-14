# Quickstart Validation: Count over Content

**Feature**: 012-count-over-content | **Date**: 2026-10-14

Runnable end-to-end validation for the feature. Contracts referenced:
[count-query](contracts/count-query.md),
[routing](contracts/routing.md),
[evaluation](contracts/evaluation.md).

## Prerequisites

1. Stack healthy: `docker compose up -d` (PostgreSQL pgvector/pgvector:pg16,
   GraphJin 3.21.6), `.env` configured with the pinned chat AND embedding
   endpoint values.
2. Feature 010 + 011 complete: governed retrieval and classifier-based
   content routing work (verified per their quickstarts).
3. The +5 dev and +6 held-out count-over-content cases are present in
   `evaluation/dev_cases.json` and `evaluation/cases.json`.

## Step 1 — Noise calibration (threshold setting)

Run the held-out evaluation on the CURRENT program 2-3 times at temperature
0 and record the count-relevant noise band:

```bash
python -m evaluation.run --cache=false --output /tmp/eval_cal_1.json
python -m evaluation.run --cache=false --output /tmp/eval_cal_2.json
```

Expected: the observed variance is recorded; the count-accuracy and
false-count thresholds are set ABOVE the noise band and recorded.

## Step 2 — Semantic threshold calibration (dev-only)

```bash
python -m app.ai.count_calibration   # or the documented entry point
```

Expected: the deterministic sweep consumes ONLY development count cases (the
leakage guard passes), picks the threshold maximizing exact-count accuracy
on dev, and writes `count-threshold.json` (threshold, version, method, dev
IDs, created_at, SHA-256).

## Step 3 — Count smoke test (live)

Through the conversational query path (`POST /query`):

- "how many tickets about login" -> the TRUE count (lexical + semantic), NOT
  0 and NOT 25.
- "how many tickets are about sign-in problems" -> includes semantic matches
  (paraphrase count).
- "how many P1 tickets are there?" -> structured path, unchanged (112).
- "how many tickets contain passwords" -> nothing prohibited; trace hygiene.

Expected: count-over-content returns true totals; structured counts
unchanged; the trace shows the count + up to 5 example ids.

## Step 4 — Held-out evaluation + comparison

```bash
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

Expected: count accuracy >= calibrated threshold; false-count rate <=
calibrated bound; the structured execution-accuracy gate does NOT regress;
security count cases return nothing prohibited; zero held-out IDs in the
calibration input. If count accuracy does NOT reach the threshold: STOP AND
REPORT to the human.

## Step 5 — Full regression

```bash
pytest -q
```

Expected: all 622 pre-existing tests pass plus the new unit/integration
tests of this feature; no failures introduced.

## Done criteria mapping

Step 1 -> SC-004/SC-006 (thresholds); Step 2 -> SC-007 (calibration
discipline); Step 3 -> SC-001/SC-002/SC-003 (true/paraphrase/no-undercount)
+ SC-005 (structured unchanged); Step 4 -> SC-004/SC-005/SC-006/SC-007/SC-008;
Step 5 -> SC-009.
