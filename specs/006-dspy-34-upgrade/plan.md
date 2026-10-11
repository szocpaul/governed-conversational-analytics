# Implementation Plan: DSPy 3.4 Upgrade with Re-Baseline and Re-Optimization

**Branch**: `[006-dspy-34-upgrade]` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-dspy-34-upgrade/spec.md`

## Summary

Upgrade the pinned DSPy dependency from 3.2.1 to 3.4.0 and re-establish the project's measured quality state on the new runtime: preserve the 3.2.1 baseline and optimized program under dated names, verify the LLM endpoint and deprecation surface on 3.4, record a new baseline under feature 004 discipline, re-run the approved BootstrapFewShot optimization (dev cases only, unchanged config), pass the same-version comparison gate, and produce a cross-version (3.2.1 vs 3.4.0) report as human decision input. The deterministic validator, governed read-only surface, evaluation case files, metric, and optimizer configuration are all unchanged — only the DSPy runtime version and the measured artifacts change.

## Technical Context

**Language/Version**: Python — see research.md D1. The feature 005 baseline ran on Python 3.12; the host now exposes `/usr/bin/python3` = Python 3.14.4 and the 3.12 binary is gone, so the project dependencies (including `dspy==3.4.0`) must be installed and verified on Python 3.14.

**Primary Dependencies**: `dspy==3.4.0` (upgraded pin; PyPI-verified available), plus the existing unchanged pins: fastapi 0.143.0, uvicorn[standard] 0.45.0, pydantic 2.12.5, httpx 0.28.1, pytest 9.0.3, python-dotenv. Any other dependency change must be required by the DSPy pin (FR-001).

**Storage**: PostgreSQL (pinned image, port 5432) via GraphJin (port 8081) — unchanged; this feature touches no schema or data. Versioned JSON artifacts under `artifacts/` and `app/ai/optimized_program.json`.

**Testing**: pytest (`python3 -m pytest -q`), the evaluation runner (`python3 -m evaluation.run`), the comparison gate (`python3 -m evaluation.compare`), and the optimization runner (`python3 -m app.ai.optimization`) — all existing entry points, unchanged.

**Target Platform**: Linux server (the project's existing host), local llama.cpp OpenAI-compatible endpoint.

**Project Type**: web-service (FastAPI) with a governed conversational analytics pipeline; this feature is a runtime-upgrade + re-measurement feature, not a surface change.

**Performance Goals**: none gated — latency remains observational only (per-request, median, p90, maximum reported in baseline and cross-version report).

**Constraints**: zero DSPy deprecation warnings in measured runs before any baseline is recorded (FR-004); zero held-out IDs consumed by optimization (FR-010); no GEPA/MIPROv2/SIMBA/fine-tuning (FR-011); same pinned local model and endpoint (FR-002); stop-and-report instead of workaround if 3.4 cannot run cleanly (FR-013).

**Scale/Scope**: one dependency pin change, artifact preservation, one preflight re-run, full test suite, one baseline, one optimization run, one held-out evaluation, one cross-version report, doc pin updates.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`.specify/memory/constitution.md`) is the unfilled spec-kit template; the de facto governance document is `AGENTS.md` (per its Source-of-Truth Precedence, approved spec > plan > tasks > AGENTS.md). Checking this plan against AGENTS.md:

- **Baseline discipline** (new baseline on runtime version change): satisfied — the entire feature is the disciplined re-baseline (FR-005/FR-006).
- **Approved optimizer only** (`dspy.BootstrapFewShot`, bounded config, dev-only, >=12 examples): satisfied — FR-007 reuses the unchanged approved configuration; GEPA prohibited (FR-011) even though 3.4 ships it.
- **Held-out isolation**: satisfied — FR-010; the existing guards in `app/ai/optimization.py` remain.
- **No arbitrary SQL / read-only governed path**: satisfied — no change to the query path.
- **No provider/model switch**: satisfied — FR-002 re-verifies the same pinned local model.
- **Secrets / endpoint hygiene**: satisfied — preflight saves non-secret metadata only; no endpoint exposure in UI/errors/traces.
- **Stop-and-report conditions**: satisfied — FR-013 plus the deprecation-internal nuance in FR-004.
- **MANUAL GATE discipline**: satisfied — gates at spec (passed), post-plan/tasks approval, and pre/post-implementation review; no gate is ticked by the agent.

No violations. Complexity Tracking: not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-dspy-34-upgrade/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
├── checklists/
│   └── requirements.md  # Specify-phase quality checklist (complete)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
requirements.txt              # dspy pin 3.2.1 -> 3.4.0 (only intended code-adjacent change)
app/
├── ai/
│   ├── llm.py                # LM configuration; deprecation-surface check point (FR-004)
│   ├── optimization.py       # approved BootstrapFewShot runner; unchanged config
│   ├── query_program.py      # planner program; unchanged
│   ├── answer_program.py     # grounding program; unchanged
│   └── optimized_program.json  # recompiled on 3.4; 3.2.1 copy preserved dated
├── api/routes.py             # loads optimized program (state-only .load); unchanged
└── ...
evaluation/                   # run.py / compare.py / cases — unchanged entry points
artifacts/                    # baseline.json, current.json, optimization-run.json,
                              # llm-preflight.json regenerated; *-pre-006-*.json preserved
tests/                        # full suite must pass on 3.4 (FR-003)
README.md, AGENTS.md          # pin/status updates (FR-012)
```

**Structure Decision**: existing single-project layout; no new modules are anticipated. If the deprecation cleanup (FR-004) requires code changes, they are expected to be confined to `app/ai/llm.py` (LM construction) — anything larger triggers the stop-and-report evaluation in FR-013.

## Phases

### Phase 0: Research

See [research.md](research.md). Decisions:

- **D1**: Interpreter/dependency strategy on Python 3.14 — install the pinned requirements with `dspy==3.4.0` on the host Python 3.14 and verify importability; if any pinned dependency cannot install/run on 3.14, stop and report.
- **D2**: Deprecation-surface detection — run measured entry points under `python3 -W default::DeprecationWarning` (per dspy-fundamentals 3.5-migration guidance) and treat any DSPy deprecation warning as a finding to fix before baseline.
- **D3**: LM configuration on 3.4 — keep the standard LiteLLM-style path (`dspy.LM(model="openai/<id>", api_base=..., model_type="chat")`); do not adopt `engine=`/lm15 native engines (out of scope); only adjust if a deprecation warning is traced to this callsite. Follow-up candidate (deferred to a future spec): evaluate the new DSPy 3.4 features — Flex, ReActV2, native engines/lm15 (including the LM-path migration before the DSPy 3.5 removal deadline), TypeSafe, MCP support — for their usefulness to this project; see `specs/007-dspy-34-feature-evaluation-sketch.md`.
- **D4**: Saved-program compatibility — assume the 3.2.1 state-only `optimized_program.json` does not round-trip on 3.4; preserve it dated and recompile via re-optimization; verify load of the newly compiled artifact at startup.
- **D5**: Baseline/optimization/evaluation procedure — reuse the feature 004/005 commands and discipline unchanged (temperature 0, cache off, 2-3 noise samples, full held-out run, approved BootstrapFewShot config, compare gate).
- **D6**: Cross-version report — new small artifact comparing preserved 3.2.1 results with 3.4.0 results across the spec'd dimensions; human review item, not gated.

### Phase 1: Design & Contracts

See [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

- **data-model.md**: the feature's entities are versioned artifacts (baseline, optimized program, optimization run record, cross-version report, preflight record) — no database entities change.
- **contracts/**: artifact format contracts (what each regenerated/preserved artifact must contain) and the validation-command contract.
- **quickstart.md**: the end-to-end validation sequence proving the feature (install → preflight → tests → preservation → baseline → optimization → held-out → compare → cross-version report).

## Post-Design Constitution Check

Re-checked after Phase 1: the design introduces no new runtime components, no new query-surface behavior, no new optimizer, and no new external interface. All AGENTS.md gates remain satisfied. No violations.
