# Feature Specification: DSPy 3.4 Upgrade with Re-Baseline and Re-Optimization

**Feature Branch**: `[006-dspy-34-upgrade]`

**Created**: 2026-10-11

**Status**: Approved

**Input**: User description: "Upgrade the project's pinned DSPy dependency from 3.2.1 to 3.4.0. Because all baselines, the compiled optimized program, and held-out results were measured on 3.2.1, and the project's baseline discipline requires a new baseline on any runtime version change, this is a full re-baseline + re-optimization feature, not a dependency bump. See specs/006-dspy-upgrade-sketch.md."

## Background (Diagnosis)

The project pins `dspy==3.2.1`. PyPI latest is 3.4.0 (2026-09-25), and DSPy 3.4 is the transition release for the LM integration layer: legacy custom-LM integrations and OpenAI-style `messages=` calls remain in 3.4 with deprecation warnings, and DSPy 3.5 will remove the legacy path. The project uses the standard LiteLLM-style path (`dspy.LM(model="openai/<id>", api_base=..., model_type="chat")`) against the local llama.cpp OpenAI-compatible endpoint, so it should keep working, but the deprecation surface must be verified in measured runs.

Two assets are version-sensitive:

- `artifacts/baseline.json` and all held-out results were measured under DSPy 3.2.1; per the project's baseline discipline they are not comparable to runs under a different DSPy version.
- `app/ai/optimized_program.json` was compiled by DSPy 3.2.1; saved-program load/save may not round-trip across versions, so it must be assumed to require recompilation on 3.4.

The API surface the project uses (`Signature`, `InputField`/`OutputField`, `Predict`, `ChainOfThought`, `Module`, `Example`, `Prediction`, `BootstrapFewShot`, `settings`, `configure`, `LM`) contains none of the flagged 3.3/3.4 breaking areas. BootstrapFewShot received bugfixes in 3.4, so accepted demonstration sets may differ from the 3.2.1 run; this is expected and is handled by re-optimization, not by reusing the old artifact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Runtime Upgrade Without Behavior Breakage (Priority: P1)

As the project maintainer, I want the conversational analytics pipeline to run on DSPy 3.4.0 with the full test suite passing and zero deprecation warnings in measured runs, so that the project is off the legacy LM path before DSPy 3.5 removes it.

**Why this priority**: Everything else in the feature (re-baseline, re-optimization, comparison) depends on a working 3.4 runtime. If the pipeline cannot run cleanly on 3.4, the feature stops and reports.

**Independent Test**: Pin `dspy==3.4.0`, run the full test suite and a measured evaluation sample, and verify all tests pass and no DSPy deprecation warnings appear in measured-run output.

**Acceptance Scenarios**:

1. **Given** the repository with `dspy==3.4.0` pinned, **When** the full test suite runs, **Then** all tests pass.
2. **Given** the upgraded runtime, **When** a measured evaluation run executes (temperature zero, cache disabled), **Then** its output contains zero DSPy deprecation warnings.
3. **Given** the upgraded runtime, **When** the LLM preflight is re-run against the local endpoint, **Then** the exact pinned model ID is verified, a deterministic smoke chat completion succeeds, a typed DSPy prediction succeeds, and non-secret metadata is saved to `artifacts/llm-preflight.json`.
4. **Given** a deprecation warning or program load/save breakage that cannot be fixed within scope, **When** it is encountered, **Then** the feature stops and reports with the option to stay on 3.2.1, instead of improvising a workaround.

---

### User Story 2 - Preservation of Pre-Upgrade Evidence (Priority: P1)

As the project maintainer, I want the 3.2.1 baseline and optimized program preserved under dated names before any re-measurement, so that cross-version comparison remains possible and the pre-upgrade state is never overwritten.

**Why this priority**: The pre-upgrade artifacts are the only record of the approved 3.2.1 quality state; losing them makes the cross-version report impossible and destroys approved evidence.

**Independent Test**: After the preservation step, verify that dated copies of the baseline and optimized program exist (same `*-pre-006-YYYY-MM-DD.json` convention as feature 005) and that the originals' checksums match the copies.

**Acceptance Scenarios**:

1. **Given** the pre-upgrade repository state, **When** preservation runs, **Then** `artifacts/baseline.json` and `app/ai/optimized_program.json` are copied to dated `*-pre-006-YYYY-MM-DD.json` names and the copies are byte-identical to the originals.
2. **Given** the preserved artifacts, **When** re-optimization produces a new `app/ai/optimized_program.json`, **Then** the dated pre-upgrade copy remains untouched.

---

### User Story 3 - Re-Baseline Under Feature 004 Discipline (Priority: P1)

As the project maintainer, I want a new baseline recorded on DSPy 3.4.0 under the same discipline as feature 004 (temperature zero, cache disabled, repeated samples for noise, full held-out run), so that the 3.4 quality state is measured with the same rigor as the approved 3.2.1 state.

**Why this priority**: The new baseline is the reference for the re-optimization comparison gate and for the cross-version report; without it no quality claim about 3.4 is possible.

**Independent Test**: Verify `artifacts/baseline.json` is regenerated on 3.4.0 with pinned metadata, noise recorded from 2-3 repeated samples, and a complete held-out run.

**Acceptance Scenarios**:

1. **Given** the upgraded runtime, **When** the baseline is recorded, **Then** measured runs use temperature zero and disabled model-response caching, a representative sample is run 2-3 times with per-metric noise recorded, and the complete held-out evaluation is executed.
2. **Given** the new baseline, **When** its metadata is inspected, **Then** it records the DSPy version, the exact API model ID, and the artifact hashes required by the project's artifact discipline.

---

### User Story 4 - Re-Optimization and Held-Out Evaluation on 3.4 (Priority: P1)

As the project maintainer, I want the approved BootstrapFewShot optimization re-run on DSPy 3.4.0 with the unchanged approved configuration and only development examples, followed by a held-out evaluation, so that the optimized program on 3.4 is produced under the same rules as the approved 3.2.1 program.

**Why this priority**: The optimized program is what serves user queries; it must be recompiled and re-validated on the new runtime under the same governance as before.

**Independent Test**: Verify `artifacts/optimization-run.json` records the run (inputs, accepted demonstration IDs, configuration, output artifact hash, errors, versions), that only development case IDs were consumed, and that the post-optimization held-out evaluation produces `artifacts/current.json`.

**Acceptance Scenarios**:

1. **Given** at least 12 valid labeled development examples, **When** optimization runs, **Then** it uses the approved BootstrapFewShot configuration unchanged (metric_threshold 1.0, max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors 3) and consumes development cases only.
2. **Given** the re-optimized program, **When** the held-out evaluation runs with temperature zero and cache disabled, **Then** `artifacts/current.json` is produced and the comparison gate against the new 3.4 baseline passes: no failed P1 quality thresholds, no execution-accuracy degradation greater than 5 percentage points, no prohibited database effect, no unauthorized disclosure.
3. **Given** the optimization run, **When** its consumed example IDs are inspected, **Then** zero held-out IDs appear.

---

### User Story 5 - Cross-Version Quality Report (Priority: P2)

As the project maintainer, I want a report comparing the 3.4.0 post-optimization results against the preserved 3.2.1 results (validity, accuracy, security metrics, false refusals, observational latency), so that a human can decide whether the upgrade maintains quality.

**Why this priority**: The cross-version delta is the decision input for accepting the upgrade, but per the sketch it is a human review item, not an automatic rollback trigger; the automatic gate is the same-version comparison.

**Independent Test**: Verify the cross-version report exists, covers validity, accuracy, security metrics, false refusals, and per-request/median/p90/max latency, and is produced from the preserved 3.2.1 artifacts and the new 3.4 artifacts.

**Acceptance Scenarios**:

1. **Given** the preserved 3.2.1 results and the new 3.4.0 results, **When** the cross-version report is produced, **Then** it reports validity, accuracy, security metrics, false-refusal rate, and observational latency for both versions.
2. **Given** a quality regression versus 3.2.1 in the report, **When** the feature reaches its manual gate, **Then** the regression is presented as a human decision point and is not silently accepted or automatically rolled back.

---

### Edge Cases

- DSPy 3.4 emits a deprecation warning on the project's LM path during a measured run: this is a finding that must be resolved or stop the feature, since zero deprecation warnings in measured runs is the target.
- The 3.2.1-compiled `optimized_program.json` fails to load under 3.4: expected possibility; the feature recompiles it via re-optimization rather than patching the old artifact.
- BootstrapFewShot on 3.4 accepts a different demonstration set than on 3.2.1: expected due to upstream bugfixes; the new accepted set is recorded in `artifacts/optimization-run.json`.
- Fewer than 12 valid labeled development examples exist: optimization must not run, per the project's optimizer discipline; the feature stops and reports.
- The cross-version report shows a quality regression versus 3.2.1: this is a human decision point at the manual gate, not an automatic failure or rollback.
- Upgrading DSPy forces upgrades of other dependencies: only upgrades required by the DSPy pin are in scope; anything else is reported.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST pin `dspy==3.4.0` in requirements.txt, and any other dependency changes MUST be limited to those required by the DSPy pin.
- **FR-002**: The LLM preflight MUST be re-run on the upgraded runtime: verify the exact pinned model ID via `/v1/models`, run one deterministic chat-completion smoke request, run one typed DSPy prediction, and save non-secret metadata to `artifacts/llm-preflight.json`. The same pinned local model and endpoint MUST be used; no provider or model switch.
- **FR-003**: The full test suite MUST pass on DSPy 3.4.0.
- **FR-004**: Measured runs on DSPy 3.4.0 MUST produce zero DSPy deprecation warnings, and eliminating them is in-scope for this feature: no baseline is recorded until measured runs are warning-free. If a deprecation warning originates inside DSPy itself and cannot be removed from the application side, the feature MUST stop and report rather than ship a workaround or defer silently.
- **FR-005**: Before any re-measurement, `artifacts/baseline.json` and `app/ai/optimized_program.json` MUST be preserved under dated `*-pre-006-YYYY-MM-DD.json` names, byte-identical to the originals.
- **FR-006**: A new baseline MUST be recorded on DSPy 3.4.0 under feature 004 discipline: temperature zero, model-response caching disabled, a representative sample run 2-3 times with per-metric noise recorded, then the complete held-out evaluation, saved to `artifacts/baseline.json`.
- **FR-007**: The approved BootstrapFewShot optimization MUST be re-run with the unchanged approved configuration, only if at least 12 valid labeled development examples exist, consuming development cases only; the run's inputs, accepted demonstration IDs, configuration, output artifact hash, errors, and versions MUST be saved to `artifacts/optimization-run.json`.
- **FR-008**: After re-optimization, the unchanged held-out set MUST be evaluated with temperature zero and cache disabled, producing `artifacts/current.json`, and the comparison gate against the new 3.4 baseline MUST pass: no failed P1 quality thresholds, no execution-accuracy degradation greater than 5 percentage points, no prohibited database effect, no unauthorized disclosure.
- **FR-009**: A cross-version report MUST be produced comparing the preserved 3.2.1 results with the 3.4.0 post-optimization results, covering validity, accuracy, security metrics, false-refusal rate, and observational latency (per-request, median, p90, maximum). The cross-version delta is a human review item at the manual gate: it is reported, never automatically gated, and a regression versus 3.2.1 is neither silently accepted nor automatically rolled back.
- **FR-010**: Held-out isolation MUST remain intact: zero held-out case IDs consumed by optimization, and the development and held-out case files remain physically separate and versioned.
- **FR-011**: All feature behavior MUST remain within the governed read-only surface: no arbitrary SQL, no writable database path, no GEPA/MIPROv2/SIMBA/fine-tuning (including DSPy 3.4's GEPA), and latency remains observational only.
- **FR-012**: README and AGENTS.md pins and status MUST be updated to reflect DSPy 3.4.0 and the new baseline/optimization artifacts.
- **FR-013**: If DSPy 3.4 cannot run the pipeline without deprecation warnings, or breaks program load/save in a way that cannot be fixed within scope, the feature MUST stop and report with the option to stay on 3.2.1, rather than improvising a workaround.

### Key Entities *(include if feature involves data)*

- **Baseline artifact**: the versioned record of held-out evaluation results under a specific runtime; regenerated on 3.4.0, with the 3.2.1 version preserved under a dated name.
- **Optimized program artifact**: the compiled DSPy program produced by the approved optimizer; recompiled on 3.4.0, with the 3.2.1 version preserved under a dated name.
- **Optimization run record**: the versioned record of optimizer inputs, accepted demonstration IDs, configuration, output hash, errors, and versions.
- **Cross-version report**: the comparison of 3.2.1 versus 3.4.0 results used as human decision input.
- **Evaluation case sets**: the physically separate, versioned development and held-out case files; unchanged in content by this feature, consumed under the existing isolation rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the test suite passes on DSPy 3.4.0.
- **SC-002**: Measured runs on DSPy 3.4.0 produce zero DSPy deprecation warnings before any baseline is recorded.
- **SC-003**: 100% of pre-upgrade artifacts (baseline, optimized program) are preserved byte-identical under dated names before re-measurement.
- **SC-004**: A new baseline is recorded on 3.4.0 with temperature zero, cache disabled, 2-3 repeated noise samples, and a complete held-out run.
- **SC-005**: Re-optimization consumes zero held-out case IDs and records its full run metadata; the post-optimization comparison gate passes with no failed P1 thresholds, no execution-accuracy degradation greater than 5 percentage points, no prohibited effect, and no unauthorized disclosure.
- **SC-006**: The cross-version report covers 100% of the required dimensions (validity, accuracy, security metrics, false refusals, latency) for both versions.

## Assumptions

- Features 001-005 remain complete and unchanged; this feature changes the DSPy runtime version and re-measures, it does not change query-surface behavior.
- The pinned local model, endpoint, and dataset remain unchanged; the LLM endpoint is verified by re-running the existing preflight.
- The evaluation case files (development and held-out) are unchanged in content; only the runtime version changes.
- The project's approved BootstrapFewShot configuration and metric are reused unchanged.
- The deprecation surface of the project's DSPy usage is small (standard LiteLLM-style LM path plus the listed API surface), as verified by grep in the sketch.

## Out of Scope

- Adopting new DSPy 3.4 features (Flex, ReActV2, native engines, TypeSafe, MCP support).
- Upgrading dependencies not required by the DSPy pin.
- Model upgrade or re-quantization of the local GGUF.
- GEPA, MIPROv2, SIMBA, or any fine-tuning.
- Latency targets (latency remains observational only).

## MANUAL GATE 1: Specification Review

- [x] Human reviewer approves this specification before planning begins. **Approved 2026-10-11.**
