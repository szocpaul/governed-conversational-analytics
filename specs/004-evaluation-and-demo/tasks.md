# Tasks: Evaluation, Optimization, and Demo Experience

**Spec**: `specs/004-evaluation-and-demo/spec.md`  
**Plan**: `specs/004-evaluation-and-demo/plan.md`

## Phase 1: Datasets and Metrics

- [X] **T001 [P] [US1] [US3]** Create separate versioned `evaluation/dev_cases.json` and `evaluation/cases.json` with stable IDs; include 12-20 labeled development cases and at least 20 held-out cases, including at least 5 security or unauthorized-access cases.
- [X] **T002 [P] [US1]** Write failing deterministic metric tests in `tests/evaluation/test_metrics.py`, then implement structural validity, normalized execution accuracy, security effects, disclosure, false refusals, and observational latency in `evaluation/metrics.py`.
- [X] **T003 [P] [US1] [US2]** Write failing artifact and regression tests in `tests/evaluation/test_regression_gate.py`, then implement versioned metadata, uncached evaluation output, and exit-code comparison in `evaluation/run.py` and `evaluation/compare.py`.

## Phase 2: Baseline and BootstrapFewShot

- [X] **T004 [US1]** Run a representative sample two or three times with the pinned model, temperature zero, and cache disabled; record per-metric noise, then write the complete pre-optimization held-out baseline to `artifacts/baseline.json`.
- [X] **T005 [US3]** Write failing optimizer metric and isolation tests in `tests/evaluation/test_optimizer_metric.py` and `tests/evaluation/test_optimization_isolation.py`, then implement `text_to_query_metric` and development/held-out ID guards in `app/ai/optimization.py`.
- [X] **T006 [US3]** Compile `dspy.BootstrapFewShot` with `metric_threshold=1.0`, `max_bootstrapped_demos=4`, `max_labeled_demos=4`, `max_rounds=1`, and `max_errors=3`, using only development cases; save the optimized program and `artifacts/optimization-run.json`. Do not run GEPA, MIPROv2, or SIMBA.
- [X] **T007 [US1] [US2]** Run the unchanged held-out set using the optimized program with temperature zero and cache disabled; save `artifacts/current.json` and verify all quality/security gates while reporting latency observationally.

## Phase 3: Demo Interface and Closure

- [X] **T008 [P] [US4]** Write failing interface tests in `tests/integration/test_demo_interface.py`, then implement the FastAPI-served UI in `app/web/index.html`, `app/web/app.js`, and `app/web/styles.css` with answer/refusal, sanitized trace, and observational latency.
- [X] **T009** Run the complete evaluation, comparison, optimizer-isolation, security, and interface gates; document datasets, optimizer configuration, baseline/current metrics, limitations, and demo scenarios in `quickstart.md` and `README.md`.
- [ ] **T010 MANUAL GATE** Human reviewer runs the three demo scenarios, reviews optimizer isolation, baseline/current artifacts, security results, and latency reporting, and approves or rejects the release. The implementation agent MUST NOT tick this task.

## Dependencies

1. T001-T003 may run in parallel after specs 001-003 are complete.
2. T004 depends on T001-T003.
3. T005 depends on T001-T003 and may start after baseline infrastructure exists.
4. T006 depends on T004-T005 and requires at least 12 valid development cases.
5. T007 depends on T006.
6. T008 may run after the existing API is stable and in parallel with T004-T007.
7. T009 depends on T007-T008; T010 depends on T009.

## Validation Gates

```bash
pytest -q tests/evaluation tests/integration/test_demo_interface.py
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

## MANUAL GATE 3: Task Review

- **Approved**
