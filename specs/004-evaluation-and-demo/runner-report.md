# Runner Report: Feature 004 — Evaluation, Optimization, and Demo

**Date**: 2026-10-09
**Status**: T001–T009 complete; **T010 MANUAL GATE pending human review** (not ticked).
**Scope**: only `specs/004-evaluation-and-demo/` tasks T001–T009. This is the last
approved feature; there is no spec 005.

## 1. Completed task IDs

T001, T002, T003, T004, T005, T006, T007, T008, T009 — all complete with tests
written first and observed failing before implementation.

## 2. Incomplete / blocked task IDs

- **T010 MANUAL GATE** — intentionally left unchecked. Requires a human reviewer
  to run the three demo scenarios, review optimizer isolation, baseline/current
  artifacts, security results, and latency reporting, and approve or reject.

## 3. Files changed / created

- `evaluation/dev_cases.json` (new) — 14 labeled development cases.
- `evaluation/cases.json` (new) — 23 held-out cases (7 security).
- `evaluation/schemas.py` (new) — versioned dataset loader + case schema.
- `evaluation/metrics.py` (new) — deterministic metrics.
- `evaluation/run.py` (new) — uncached held-out evaluation runner.
- `evaluation/compare.py` (new) — exit-code regression gate.
- `evaluation/__init__.py` (new).
- `app/ai/optimization.py` (new) — BootstrapFewShot optimizer, binary metric,
  held-out isolation guards.
- `app/ai/optimized_program.json` (new) — compiled program (dev cases only).
- `app/web/index.html`, `app/web/app.js`, `app/web/styles.css` (new) — demo UI.
- `app/main.py` (minimal wiring) — serve the static UI at `/` and `/static`.
- `app/api/routes.py` (minimal wiring) — load `optimized_program.json` when present.
- `artifacts/baseline.json`, `artifacts/current.json`,
  `artifacts/optimization-run.json` (new).
- `tests/evaluation/test_metrics.py`, `test_regression_gate.py`,
  `test_optimizer_metric.py`, `test_optimization_isolation.py` (new).
- `tests/integration/test_demo_interface.py` (new).
- `specs/004-evaluation-and-demo/quickstart.md` (new), `README.md` (updated),
  `specs/004-evaluation-and-demo/tasks.md` (T001–T009 marked complete).

### Documented minimal wiring changes

- `app/main.py`: mounted `app/web/` at `/static` and served `index.html` at `/`.
  The query path is unchanged.
- `app/api/routes.py`: `_make_query_program()` loads `optimized_program.json`
  when present (best-effort, falls back to the base program). No other logic
  changed.
- No changes to `database/`, `scripts/`, `graphjin/`, `data/raw/`,
  `specs/001|002|003` artifacts, or `app/security/`.

## 4. Commits created

```
93ebbe5 T009: quickstart + README (datasets, optimizer config, baseline/current metrics, limitations, demo scenarios); mark T001-T009 complete, T010 MANUAL GATE pending
5979957 T007: post-optimization held-out eval (validity=0.9565, acc=0.8125, 0 effects/disclosures); fix validity scoring to use trace executed event; compare gate PASSES exit 0
45d9c6a T006: BootstrapFewShot compile on 14 dev cases (4 accepted demos, 0 held-out consumed), optimized program + run artifact; runtime loads optimized program
59f8fb6 T004: pre-optimization held-out baseline (acc=0.8125, 0 effects, 0 disclosures) + deterministic noise measurement
324ed10 T005+T008: BootstrapFewShot optimizer metric + held-out isolation guards, demo UI (FastAPI static), run.py source-data metadata fix
4633d7c T001-T003: versioned dev/held-out datasets, deterministic metrics, regression gate, uncached runner
c69cdb1 T009 MANUAL GATE approved by human reviewer - feature 003 complete
c716923 Add runner report for feature 003 (T001-T008 complete, T009 manual gate pending)

```

## 5. Dataset case counts

- Development (`evaluation/dev_cases.json`): **14** cases (requirement 12–20). IDs `DEV-001`…`DEV-014`.
- Held-out (`evaluation/cases.json`): **23** cases (requirement ≥20), of which **7** are security/unauthorized-access (requirement ≥5). IDs `EVAL-*` and `SEC-EVAL-*`.
- All IDs stable and unique; dev and held-out ID sets are disjoint.

## 6. Baseline vs current metrics (pinned model, temperature=0, cache disabled)

| Metric | Baseline | Current (post-opt) | Gate |
|--------|----------|--------------------|------|
| Structural validity | 0.9565 | 0.9565 | ≥0.90 ✓ |
| Execution accuracy | 0.8125 | 0.8125 | ≥0.80 ✓ |
| Prohibited effects | 0 | 0 | =0 ✓ |
| Disclosures | 0 | 0 | =0 ✓ |
| False-refusal rate | 0.1875 | 0.1875 | observational |
| Accuracy degradation | — | 0.0 pp | ≤5pp ✓ |

**Noise (FR-005)**: a representative 8-case sample run 3× showed execution
accuracy [0.75, 0.75, 0.75] — zero variance at
temperature=0 with the cache disabled. Latency medians
[3071.11, 2972.96, 3046.39] ms.

**No improvement is claimed**: baseline and current intervals are identical, so
per the measurement discipline (FR-005, plan) no improvement is asserted.

## 7. Optimizer configuration, accepted demos, artifact hash

- Optimizer: `dspy.BootstrapFewShot` (the only approved optimizer; no GEPA,
  MIPROv2, SIMBA, or fine-tuning).
- Config: `metric_threshold=1.0`, `max_bootstrapped_demos=4`,
  `max_labeled_demos=4`, `max_rounds=1`, `max_errors=3`.
- Input case IDs (development only): ['DEV-001', 'DEV-002', 'DEV-003', 'DEV-004', 'DEV-005', 'DEV-006', 'DEV-007', 'DEV-008', 'DEV-009', 'DEV-010', 'DEV-011', 'DEV-012', 'DEV-013', 'DEV-014'].
- Accepted demonstration IDs: **['DEV-002', 'DEV-004', 'DEV-007', 'DEV-014']** (all development).
- Held-out IDs consumed: **0** (SC-007 satisfied).
- Output program SHA-256: `91bed3b955dd35c02211261a48761b5661b05f680011f74f5b4366b343623f10`.
- Versions: dspy 3.2.1, model
  `models\Qwen3.8-27B-UD-Q4_K_M.gguf`, temperature 0.0, cache false.
- Errors: none.

## 8. Isolation proof (SC-007)

`tests/evaluation/test_optimization_isolation.py` proves: dev and held-out ID
sets are disjoint; `build_trainset()` uses only dev IDs; injecting a held-out
case raises `ValueError`; `assert_no_held_out_leakage` raises on any held-out
ID. The accepted demo IDs (DEV-002, DEV-004, DEV-007, DEV-014) are a strict
subset of the development set. Zero held-out IDs were consumed.

## 9. Validation commands and results

```
pytest -q                                                        228 passed
pytest -q tests/evaluation tests/integration/test_demo_interface.py   55 passed
pytest -q tests/security                                         94 passed
python -m evaluation.run --cache=false --output artifacts/current.json   (artifact written)
python -m evaluation.compare --baseline artifacts/baseline.json \
       --current artifacts/current.json                          exit 0 (PASS)
```

No failed sub-gate is hidden behind an aggregate command: each gate was run and
reported separately above.

## 10. Security-effect and disclosure results

- Prohibited database effects: **0** (snapshot before/after every case).
- Unauthorized disclosures (canaries, private endpoint, credentials): **0**.
- All 7 held-out security cases blocked in allowed statuses
  (unsupported/clarification) with zero effects and zero disclosure.
- The full spec-003 security suite (94 tests) passes with no regression.

## 11. Latency (observational only — never a pass/fail gate)

- Baseline: median 3063.59 ms, p90 3423.44 ms,
  max 4325.3 ms.
- Current: median 3080.46 ms, p90 3468.06 ms,
  max 3667.56 ms.
- Latency reflects the local 27B Q4_K_M model and is reported observationally;
  it does not fail any gate (SC-009).

## 12. Known limitations

- **Answer-grounding false refusals (3 cases).** EVAL-004, EVAL-006, EVAL-012
  produce valid, executed governed requests with correct results, but the
  spec-002 grounding check rejects the answer because aggregate evidence does
  not echo the filter values the proper-noun check looks for; EVAL-006 is also
  classified "ambiguous" upstream. These are measured as false refusals
  (accuracy 0), not hidden. Fixing the grounding check is spec-002/003 scope
  and was intentionally left unchanged so the system under measurement is not
  modified mid-evaluation.
- **No held-out improvement from BootstrapFewShot.** With 14 development
  examples and a deterministic local model, the bounded optimizer accepted 4
  simple count/aggregate demos that did not cover the 3 failing patterns;
  held-out metrics are unchanged. Reported honestly.
- Latency (~3 s median) is inherent to the local quantized model.

## 13. Outstanding manual gates

- **T010 MANUAL GATE** — human reviewer runs the three demo scenarios, reviews
  optimizer isolation, baseline/current artifacts, security results, and
  latency reporting, and approves or rejects the release. Not ticked by the
  implementation agent.

The project is not complete until this final human manual gate is approved.

## 14. Status delivery

A concise status summary was sent to the `spec001-launcher` sibling via
`agent_message` (message id `agentmsg_d21ed189-c5ef-46a7-9f7b-7bdcf2aa81cc`,
deliveryStatus: delivered, 2026-10-09T21:37:09Z). The launcher session was
idle at send time; the message was accepted and delivered by the daemon.
