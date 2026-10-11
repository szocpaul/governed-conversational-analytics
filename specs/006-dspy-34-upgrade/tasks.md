# Tasks: DSPy 3.4 Upgrade with Re-Baseline and Re-Optimization

**Spec**: `specs/006-dspy-34-upgrade/spec.md` (approved 2026-10-11)
**Plan**: `specs/006-dspy-34-upgrade/plan.md`
**Research**: `specs/006-dspy-34-upgrade/research.md` (D1 interpreter, D2 deprecation detection, D3 LM config, D4 saved-program compatibility, D5 measurement procedure, D6 cross-version report)
**Contract**: `specs/006-dspy-34-upgrade/contracts/validation-and-artifacts.md`
**Quickstart**: `specs/006-dspy-34-upgrade/quickstart.md`

**Tests**: REQUIRED per AGENTS.md implementation workflow — write failing
tests first, observe the failure, then implement.

**Stop-and-report conditions (FR-013)**: install/import failure on the host
Python, preflight failure, test failure that cannot be fixed within scope,
unfixable or DSPy-internal deprecation warning, optimization skip/failure,
compare-gate failure, any prohibited effect or disclosure → STOP AND REPORT;
do not improvise.

## Phase 1: Setup (Runtime Preparation)

**Purpose**: get the pinned stack with `dspy==3.4.0` running on the host
interpreter (research.md D1). All later phases depend on this.

- [X] **T001** Record the pre-change state: `git log --oneline -3`, `git status`, current `requirements.txt` content, and the host interpreter facts (`python3 --version`, `python3 -m site`) into `specs/006-dspy-34-upgrade/verification-notes.md`. Note: feature 005 ran on Python 3.12 which no longer exists on the host; the live interpreter is Python 3.14.4 and `import dspy` currently fails there.
- [X] **T002** Update `requirements.txt`: change the pin `dspy==3.2.1` to `dspy==3.4.0`. Do not change any other pin unless a later task proves it required by the DSPy pin (FR-001).
- [X] **T003** Install the pinned requirements on the host interpreter (`python3 -m pip install --user -r requirements.txt`) and verify every pinned dependency imports on Python 3.14: `python3 -c "import dspy, fastapi, uvicorn, pydantic, httpx, pytest, dotenv; print(dspy.__version__)"` must print `3.4.0`. If any pinned dependency cannot install or import on Python 3.14, STOP AND REPORT (FR-013); if a required transitive pin change is needed, record it explicitly in `verification-notes.md` per FR-001.

## Phase 2: Foundational (Runtime Verification — Blocks All Measurement)

**Purpose**: prove the pipeline runs cleanly on DSPy 3.4.0 before any
artifact is preserved or re-measured. No measured run may begin until this
phase passes.

**⚠️ CRITICAL**: Phases 3-6 MUST NOT start until T004-T007 pass.

- [X] **T004** Re-run the LLM preflight on the new runtime: `python3 -m app.ai.preflight`. Verify exit 0 and that `artifacts/llm-preflight.json` records the exact pinned API model ID (same model as before — no provider/model switch, FR-002), a successful deterministic smoke chat completion, a successful typed DSPy prediction, and DSPy version 3.4.0. On any failure, STOP AND REPORT.
- [X] **T005** Run the full test suite on DSPy 3.4.0: `python3 -m pytest -q`. All tests must pass (FR-003). Fix any breakage from the DSPy upgrade with the smallest change that restores the approved behavior; record every changed file in `verification-notes.md`. If a failure cannot be fixed within scope, STOP AND REPORT.
- [X] **T006** Deprecation-surface detection (research.md D2, FR-004): run `python3 -W default::DeprecationWarning -m pytest -q` and capture the output. Any DSPy deprecation warning is a finding: trace it to its callsite and record it in `verification-notes.md`.
- [X] **T007** Eliminate every DSPy deprecation warning found in T006 (FR-004: cleanup in-scope; no baseline may be recorded until measured runs are warning-free). Expected callsite, if any: the LM construction in `app/ai/llm.py` (research.md D3 — minimal fix only, e.g. an explicit engine parameter; do NOT adopt lm15/native engines or any other new 3.4 feature). Write failing tests first where the fix changes behavior. If a warning originates inside DSPy itself and cannot be removed from the application side, STOP AND REPORT (FR-004/FR-013) — do not ship a workaround (e.g. warning filters that hide the warning count as a workaround and are prohibited).

## Phase 3: User Story 2 — Preservation of Pre-Upgrade Evidence (P1)

**Goal**: the 3.2.1-era measured state is preserved byte-identical under
dated names before any re-measurement (FR-005).

**Independent test**: dated `*-pre-006-*.json` copies exist and their
SHA-256 checksums match the originals.

(Story ordering note: spec US1 is delivered by Phases 1-2; this phase
implements spec US2, which must precede re-measurement.)

- [X] **T008 [US2]** Write a failing test in `tests/unit/test_artifact_preservation.py` that asserts the dated preserved copies exist and are byte-identical (SHA-256) to their sources: `artifacts/baseline.json`, `artifacts/current.json`, `artifacts/optimization-run.json`, `app/ai/optimized_program.json` → `*-pre-006-YYYY-MM-DD.json` names (feature 005 convention). Observe the failure (copies do not exist yet).
- [X] **T009 [US2]** Create the preserved copies (scripted `cp` + `sha256sum` verification is sufficient; record all four source/copy SHA-256 pairs in `verification-notes.md`) until T008 passes. These files are immutable after creation — no later task may modify them.

## Phase 4: User Story 3 — Re-Baseline Under Feature 004 Discipline (P1)

**Goal**: a new baseline on DSPy 3.4.0 recorded with the same rigor as the
approved 3.2.1 baseline (FR-006).

**Independent test**: `artifacts/baseline.json` is regenerated with DSPy
3.4.0 metadata, noise block from 2-3 repeated samples, and a complete
held-out run.

- [X] **T010 [US3]** Verify measured-run discipline before recording: temperature zero and cache disabled in the runner configuration; confirm the evaluation runner records DSPy version and Python version in the baseline metadata (extend `evaluation/run.py` metadata minimally if it does not already capture them — tests first in `tests/evaluation/` if changed).
- [X] **T011 [US3]** Record the new baseline: `python3 -W default::DeprecationWarning -m evaluation.run --cache=false --output artifacts/baseline.json` — representative sample repeated 2-3 times with per-metric noise recorded, then the complete held-out run. Verify zero DSPy deprecation warnings in the run output (FR-004). Save the run's key figures into `verification-notes.md`.

## Phase 5: User Story 4 — Re-Optimization and Held-Out Evaluation on 3.4 (P1)

**Goal**: the optimized program is recompiled on DSPy 3.4.0 under the
unchanged approved configuration, and the post-optimization held-out gate
passes (FR-007, FR-008).

**Independent test**: `artifacts/optimization-run.json` records the run with
dev-only IDs and `versions.dspy == "3.4.0"`; `evaluation.compare` exits 0.

- [X] **T012 [US4]** Run the approved optimization unchanged: `python3 -W default::DeprecationWarning -m app.ai.optimization` — `dspy.BootstrapFewShot(metric=text_to_query_metric, metric_threshold=1.0, max_bootstrapped_demos=4, max_labeled_demos=4, max_rounds=1, max_errors=3)`, development cases only. Verify `artifacts/optimization-run.json`: exit 0, `held_out_ids_consumed == 0`, accepted demo IDs ⊆ dev case IDs, output program SHA-256 recorded, `versions.dspy == "3.4.0"`. Exit 2 (fewer than 12 valid dev examples) or exit 1 is a STOP AND REPORT finding. Zero DSPy deprecation warnings in output (FR-004). Do not run GEPA, MIPROv2, or SIMBA (FR-011).
- [X] **T013 [US4]** Verify the newly compiled `app/ai/optimized_program.json` loads on 3.4.0: write a failing test first in `tests/unit/test_query_program.py` (or a new `tests/unit/test_program_loading.py`) that constructs the query program and calls `.load()` on the new artifact, asserting the loaded predictors carry demonstrations; observe it pass after recompilation. (This guards the silent-fallback risk in `app/api/routes.py` documented in research.md D4.)
- [X] **T014 [US4]** Run the post-optimization held-out evaluation: `python3 -m evaluation.run --cache=false --output artifacts/current.json` (temperature zero, cache disabled), then the comparison gate: `python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json`. The gate MUST exit 0: no failed P1 quality thresholds, no execution-accuracy degradation > 5 percentage points, no prohibited database effect, no unauthorized disclosure. Any gate failure is a STOP AND REPORT finding.

## Phase 6: User Story 5 — Cross-Version Quality Report (P2)

**Goal**: a report comparing preserved 3.2.1 results with 3.4.0
post-optimization results as human decision input (FR-009; never gated).

**Independent test**: `artifacts/cross-version-006.json` exists and covers
validity, accuracy, security metrics, false refusals, and latency for both
versions, with artifact hashes and runtime metadata.

- [X] **T015 [P] [US5]** Write failing tests in `tests/evaluation/test_cross_version_report.py` for the report generator: given two result artifact pairs (3.2.1 preserved, 3.4.0 current), the report contains per-version structural validity, execution accuracy, prohibited-effect count, unauthorized-disclosure count, false-refusal count/rate, and latency (per-request values, median, p90, maximum), plus both versions' artifact SHA-256 hashes and runtime metadata (DSPy version, Python version, model ID); the report contains NO pass/fail verdict field.
- [X] **T016 [US5]** Implement the report generator as a separate small script (e.g. `evaluation/cross_version_report.py` with a `__main__` entry) — do NOT extend `evaluation/compare.py` (research.md D6: the same-version gate's semantics stay clean). Run it against the preserved `*-pre-006-*` artifacts and the new artifacts; write `artifacts/cross-version-006.json` until T015 passes.

## Phase 7: Polish and Closure

- [X] **T017** Update `README.md` (pinned DSPy version, Python version, validation commands) and `AGENTS.md` (project status: feature 006, DSPy 3.4.0, new baseline/optimization artifacts) per FR-012. Keep the private LLM endpoint out of all user-facing docs and traces.
- [X] **T018** Run the complete validation gate set from the contract: `python3 -m pytest -q`; `python3 -m app.ai.preflight`; `python3 -m evaluation.run --cache=false --output artifacts/current.json` (already recorded — re-verify only if code changed since T014); `python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json`. Record all commands and results in `specs/006-dspy-34-upgrade/runner-report.md` (same convention as feature 005), including the final report content required by AGENTS.md (completed tasks, files changed, pinned versions, model ID, validation results, baseline/current metrics, security results, latency median/p90/max, known limitations).
- [X] **T019 MANUAL GATE** — Approved by human reviewer 2026-10-11. — Human reviewer reviews the runner report, the cross-version report (including any quality delta versus 3.2.1 — a regression is a human decision point, not an automatic rollback, FR-009), the preserved-artifact checksums, the deprecation-warning evidence, and the eval-set isolation proof, and approves or rejects the release. The implementation agent MUST NOT tick this task.

## Dependencies

1. T001 → T002 → T003 sequential (Setup).
2. Phase 2 (T004-T007) depends on T003; T004 → T005 → T006 → T007 sequential.
3. Phase 3 (T008-T009) depends on Phase 2; T008 → T009.
4. Phase 4 (T010-T011) depends on T009 (preservation must precede re-measurement); T010 → T011.
5. Phase 5 (T012-T014) depends on T011; T012 → T013 → T014.
6. Phase 6 (T015-T016) depends on T014 (needs the new artifacts) and T009 (needs the preserved artifacts); T015 and T016 are sequential with each other but the phase has no dependency on Phases 4-5 ordering beyond T014.
7. T017 may run in parallel with Phase 6 after T014. T018 depends on T016 and T017. T019 depends on T018.

## Parallel Execution Examples

- T017 (docs) in parallel with T015-T016 (cross-version report) after T014.
- Within Phase 2, no parallelism: each verification step gates the next.

## Validation Gates

```bash
python3 -m pytest -q
python3 -m app.ai.preflight
python3 -m evaluation.run --cache=false --output artifacts/current.json
python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

Deprecation-surface variants (must show zero DSPy deprecation warnings
before the baseline step is valid):

```bash
python3 -W default::DeprecationWarning -m pytest -q
python3 -W default::DeprecationWarning -m evaluation.run --cache=false --output artifacts/baseline.json
python3 -W default::DeprecationWarning -m app.ai.optimization
```

## MANUAL GATE 2: Task Review

- [x] Human reviewer approves this task list before implementation begins. **Approved 2026-10-11.** The autonomous runner MUST NOT start until this gate is approved.
