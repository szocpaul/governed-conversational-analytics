# Contract: Evaluation (routing tuning + held-out gate)

**Files**: `evaluation/dev_cases.json`, `evaluation/cases.json`,
`evaluation/metrics.py`, `app/ai/optimization.py`, `artifacts/`.

## New routing cases

- +8 development cases in `evaluation/dev_cases.json` and +10 held-out cases
  in `evaluation/cases.json`, physically separate, stable unique IDs.
- Categories: `route_content_about`, `route_content_similar`,
  `route_structured`, `route_unsupported`, plus `security_*` content cases.
- `expected`: `{"route": "<category>"}` (+ `"ticket_id": <int>` for
  content_similar; optional `"relevant_categories"` for content_about).

## Routing metric (tuning signal + held-out gate)

- Binary: 1.0 when the classifier category matches the labeled route (and,
  for content_similar, the extracted ticket_id matches), else 0.0.
- Routing accuracy = fraction of held-out routing cases correctly routed.
- False-routing rate = fraction of labeled structured cases routed to a
  content category (bounded).

## Tuning (BootstrapFewShot, dev-only)

- Approved bounded config (`optimizer_config()`): metric_threshold 1.0,
  max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors 3.
- Trainset = development routing cases ONLY; `assert_no_held_out_leakage`
  guards it (zero held-out IDs).
- Output: `app/ai/optimized_program.json` (routing demos added) +
  `artifacts/optimization-run.json` (config, accepted demo IDs, artifact
  hash, versions).

## Held-out gate (feature 004 discipline)

- Run: `python -m evaluation.run --cache=false --output artifacts/current.json`
  (temperature 0, cache disabled).
- Compare: `python -m evaluation.compare --baseline artifacts/baseline.json
  --current artifacts/current.json`.
- Gates: routing accuracy >= calibrated threshold; false-routing rate <=
  calibrated bound; the structured execution-accuracy gate MUST NOT regress;
  any prohibited effect or unauthorized disclosure fails the gate.
- Thresholds are set after a noise calibration run (measure the same
  artifact 2-3 times at temperature 0; the threshold must clear the noise
  band).
- If routing accuracy does NOT reach the threshold: STOP AND REPORT to the
  human; do not ship a degraded router; do not use GEPA/MIPROv2/SIMBA.
