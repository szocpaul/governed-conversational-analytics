# Phase 0 Research: DSPy 3.4 Upgrade

**Date**: 2026-10-11 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

All spec clarifications were resolved in the specify phase (deprecation cleanup in-scope with stop-and-report; cross-version delta is a human review item). The remaining technical unknowns are resolved below.

## D1: Interpreter and dependency installation

**Decision**: Install the pinned requirements (with `dspy==3.4.0`) on the host's current Python 3.14.4 (`/usr/bin/python3`, user-site `~/.local/lib/python3.14/site-packages`) and verify importability of every pinned dependency before any measured run.

**Rationale**: Feature 005 ran on Python 3.12 with `dspy==3.2.1` in `~/.local/lib/python3.12/site-packages`. The host has since moved: `/usr/bin/python3` is now Python 3.14.4, the `python3.12` binary no longer exists, and the 3.12 user-site is not importable from 3.14 (`import dspy` currently fails). The feature cannot run at all until the pinned stack is installed on the live interpreter. PyPI confirms `dspy 3.4.0` is available (2026-09-25). DSPy 3.4 supports current Python 3.x; pydantic 2.12.x, fastapi 0.143.x, httpx 0.28.x, and pytest 9.0.x all publish Python 3.14-compatible wheels.

**Alternatives considered**: (a) Reinstall Python 3.12 to reproduce the old environment — rejected: fighting the host OS, and the old interpreter's disappearance is a host fact, not a project choice; (b) upgrade other pins proactively — rejected: FR-001 limits changes to what the DSPy pin requires.

**Risk**: if any pinned dependency fails to install or behave on Python 3.14, that is a required-dependency change (FR-001 allows it) or, if unresolvable, a stop-and-report condition (FR-013). The interpreter change itself (3.12 → 3.14) is recorded in the new baseline metadata as part of the pinned environment.

## D2: Deprecation-surface detection method

**Decision**: Run every measured entry point (evaluation runner, optimization runner, and the test suite) under `python3 -W default::DeprecationWarning` and capture stderr; any DSPy deprecation warning in measured-run output is a finding that must be eliminated before the baseline is recorded (FR-004).

**Rationale**: Per the dspy-fundamentals skill (3.5 migration guidance), `python -W default::DeprecationWarning your_program.py` is the documented way to surface the deprecation warnings that 3.4 emits for legacy LM integrations (`lm(messages=[...])` calls, custom `BaseLM.forward()` integrations, `LegacyEngine`). Python's default warning filters hide most DeprecationWarnings, so an explicit flag is required for detection.

**Alternatives considered**: (a) relying on default warning visibility — rejected, warnings would be silently missed; (b) `-W error::DeprecationWarning` (turn warnings into hard failures) — rejected for measured runs because a single warning would abort the run; detection-then-fix gives cleaner findings. Tests may use `error` filtering selectively if useful.

## D3: LM configuration on DSPy 3.4

**Decision**: Keep the existing standard LiteLLM-style configuration in `app/ai/llm.py`: `dspy.LM(model="openai/<id>", api_base=..., api_key=..., temperature=0, cache=False, model_type="chat")` with `dspy.configure(lm=lm)`. Do not adopt the 3.4 `engine=` parameter, lm15 native engines, or `dspy.lm15.register_provider` — all out of scope (spec: no new 3.4 features).

**Rationale**: The project's LM path is the standard provider-prefixed path, which dspy-fundamentals lists as the canonical 3.4 pattern (`dspy.LM("provider/model")`); the deprecated surfaces are raw `lm(messages=[...])` calls and custom `BaseLM` subclasses, neither of which the project uses (verified by reading `app/ai/llm.py`: the only raw `messages=` usage is a direct httpx preflight call to the endpoint, not a DSPy LM call). If D2 detection nevertheless traces a warning to this callsite, the minimal fix (e.g. explicit `engine="litellm"`) is applied here; anything larger triggers FR-013 evaluation.

**Alternatives considered**: (a) migrate to lm15 native engine now — rejected: out of scope, and the compatibility backend (`engine="litellm"`) is documented as kept and supported in 3.4; (b) pin `engine="litellm"` preemptively — rejected unless D2 shows a warning: no speculative changes to a governed path.

## D4: Saved-program compatibility

**Decision**: Assume the 3.2.1-compiled `app/ai/optimized_program.json` (state-only save, `save_program=False` convention) does not round-trip across versions. Preserve it as `app/ai/optimized_program-pre-006-YYYY-MM-DD.json` (feature 005 naming convention), recompile on 3.4 via the approved re-optimization, and verify the newly compiled artifact loads at startup.

**Rationale**: dspy-fundamentals documents state-only save/load as portable JSON that requires rebuilding the architecture to load; cross-version round-trip is not guaranteed, and the sketch directs assuming recompilation. The existing loader in `app/api/routes.py` already falls back to the base program on load failure, so a stale artifact would silently degrade quality — which is exactly why preservation + recompilation is mandatory, not optional.

**Alternatives considered**: (a) attempt to load the 3.2.1 artifact on 3.4 and keep it if it loads — rejected: even if it loads, its demonstrations were selected by 3.2.1's BootstrapFewShot and the measured results would mix runtimes, violating baseline discipline; (b) full-program cloudpickle save — rejected: changes the artifact convention without need.

## D5: Baseline, optimization, and evaluation procedure

**Decision**: Reuse the feature 004/005 commands and discipline unchanged:

- Baseline: `python3 -m evaluation.run --cache=false --output artifacts/baseline.json` with temperature 0, cache disabled, 2-3 repeated samples for per-metric noise, then the complete held-out run.
- Optimization: `python3 -m app.ai.optimization` — approved `dspy.BootstrapFewShot(metric=text_to_query_metric, metric_threshold=1.0, max_bootstrapped_demos=4, max_labeled_demos=4, max_rounds=1, max_errors=3)`, dev cases only, >=12 valid labeled examples required, full run metadata to `artifacts/optimization-run.json`.
- Held-out evaluation: `python3 -m evaluation.run --cache=false --output artifacts/current.json` after optimization.
- Gate: `python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json` must exit 0 (no failed P1 thresholds, no execution-accuracy degradation > 5pp, no prohibited effect, no unauthorized disclosure).

**Rationale**: The metric, case files, and optimizer configuration are governed and unchanged by this feature (spec FR-006/FR-007/FR-008/FR-010). dspy-evaluation-harness's rule "changing the metric mid-experiment without re-baselining makes prior numbers incomparable" is honored in reverse: the metric is unchanged and the runtime changed, so the full re-baseline is what restores comparability. BootstrapFewShot's 3.4 bugfixes may change the accepted demonstration set; that is expected and recorded in `optimization-run.json`.

**Alternatives considered**: (a) adopting `dspy.Evaluate` with `save_as_json` — rejected: the project already has its own governed runner with the required metadata schema; (b) rich-feedback metric — rejected: the approved binary metric is a governance constraint (AGENTS.md), and GEPA (which needs feedback) is prohibited.

## D6: Cross-version report format

**Decision**: Produce `artifacts/cross-version-006.json` (plus a short human-readable summary in the feature's runner report) comparing the preserved 3.2.1 results (`artifacts/baseline-pre-005-2026-10-10.json` lineage — i.e. the current `artifacts/baseline.json`/`current.json` before this feature re-measures, preserved under `*-pre-006-*` names) with the new 3.4.0 results, across: structural validity, execution accuracy, security metrics (prohibited effects, unauthorized disclosures), false-refusal rate, and observational latency (per-request, median, p90, max). The report is input to the human manual gate; it is never gated automatically (spec FR-009).

**Rationale**: The spec fixes the dimensions; a JSON artifact matches the project's artifact discipline (hashes, versions recorded) and keeps the human gate decision evidence-based.

**Alternatives considered**: (a) extend `evaluation/compare.py` with a cross-version mode — rejected: compare.py is the same-version gate with hard exit codes; mixing a non-gated report into it risks confusion about what fails; a separate small report script keeps the gate's semantics clean.

## Resolved unknowns summary

No NEEDS CLARIFICATION markers remain in Technical Context. All decisions respect the spec's constraints and the AGENTS.md governance.
