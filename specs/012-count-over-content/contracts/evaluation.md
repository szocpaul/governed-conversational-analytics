# Contract: Evaluation (threshold calibration + held-out gate)

**Files**: `evaluation/dev_cases.json`, `evaluation/cases.json`,
`evaluation/metrics.py`, `app/ai/count_calibration.py`, `count-threshold.json`,
`artifacts/`.

## New count-over-content cases

- +5 development cases in `evaluation/dev_cases.json` and +6 held-out cases
  in `evaluation/cases.json`, physically separate, stable unique IDs.
- Category: `count_content` (plus a `security_*` count case).
- `expected`: `{"count": <int>}` (+ optional `"relevant_categories"`).

## Threshold calibration (deterministic, dev-only)

- A deterministic distance sweep over the development count cases: for a
  grid of candidate thresholds, embed each dev question, compute the count,
  and pick the threshold maximizing exact-count accuracy on dev (ties toward
  the larger threshold).
- Consumes development cases ONLY; `assert_no_held_out_leakage` guards it.
- Output: `count-threshold.json` (threshold, version, calibration_method,
  calibration_dev_ids, created_at, artifact_sha256). NOT a forbidden
  optimizer (no GEPA/MIPROv2/SIMBA).

## Metrics

- Count accuracy: fraction of held-out count cases where the computed count
  EXACTLY matches the labeled true count.
- False-count rate: count-over-content questions mis-routed to the
  structured path, OR structured counts mis-routed to content_count
  (bounded).

## Held-out gate (feature 004 discipline)

- Run: `python -m evaluation.run --cache=false --output artifacts/current.json`
  (temperature 0, cache disabled).
- Compare: `python -m evaluation.compare --baseline artifacts/baseline.json
  --current artifacts/current.json`.
- Gates: count accuracy >= calibrated threshold; false-count rate <=
  calibrated bound; the structured execution-accuracy gate MUST NOT regress;
  any prohibited effect or unauthorized disclosure fails the gate.
- Thresholds set after a noise calibration run (measure the same artifact
  2-3 times at temperature 0; the threshold must clear the noise band).
- If count accuracy does NOT reach the threshold: STOP AND REPORT to the
  human; do not ship an uncalibrated/degraded count.
