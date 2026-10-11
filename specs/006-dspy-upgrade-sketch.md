# Feature Sketch: DSPy 3.4 Upgrade (006)

**Status**: Sketch — not yet a full spec. Created after feature 005 closure,
from the user's deferred request ("majd később updateljük a DSPy-t").
**Depends on**: specs 001-005 complete.

## Origin

The project pins `dspy==3.2.1` (requirements.txt). PyPI latest is **3.4.0**
(2026-09-25). The pin was deliberate: the feature 004/005 baselines, the
compiled `app/ai/optimized_program.json`, and all held-out results were
measured on 3.2.1, and AGENTS.md baseline discipline requires a new baseline
on any runtime version change. Upgrading is therefore a full
re-baseline + re-optimization feature, not a dependency bump.

## What changes in 3.3/3.4 that touches this project

From the official release notes (3.3.0, 3.3.1, 3.4.0):

1. **LM transition (3.4 is the transition release; 3.5 is the migration
   deadline).** Legacy custom-LM integrations and OpenAI-style `messages=`
   calls remain in 3.4 with deprecation warnings. The project uses
   `dspy.LM(model="openai/<id>", api_base=..., model_type="chat")`
   (`app/ai/llm.py`) against the local llama.cpp OpenAI-compatible endpoint.
   This is the standard LiteLLM-style path and should keep working, but the
   deprecation surface must be checked: any warning in measured runs is a
   finding, and 3.5 will remove the legacy path.
2. **Saved-program compatibility.** `optimized.save(path)` /
   `program.load(path)` (`app/ai/optimization.py`, `app/api/routes.py`) may
   not round-trip across versions. The current
   `app/ai/optimized_program.json` was compiled by 3.2.1 — assume it must be
   recompiled on 3.4 and keep the old artifact under a dated name.
3. **API surface the project uses** (verified by grep): `Signature`,
   `InputField`/`OutputField`, `Predict`, `ChainOfThought`, `Module`,
   `Example`, `Prediction`, `BootstrapFewShot`, `settings`, `configure`,
   `LM`. None of the flagged breaking areas (Image/Audio/File constructors,
   NumPy from base install, GEPA result internals, RLM, ReActV2, Responses
   API tool calls) are used. BootstrapFewShot behavior/demonstration
   sampling had bugfixes in 3.4 — accepted demo sets may differ.
4. **Not used, no action**: Flex, ReActV2, PythonInterpreter/deno, MCP
   support, TypeSafe/Jev, native LM engines (optional in 3.4).

## Proposed scope

1. Pin `dspy==3.4.0` in requirements.txt; record the exact version and the
   llama.cpp endpoint compatibility (preflight re-run: `/v1/models`, smoke
   chat completion, one typed DSPy prediction → `artifacts/llm-preflight.json`).
2. Run the full test suite; fix any breakage from the LM transition or
   deprecations. Zero deprecation warnings in measured runs is the target.
3. Preserve `artifacts/baseline.json` and
   `app/ai/optimized_program.json` under dated names (same convention as
   feature 005: `*-pre-006-YYYY-MM-DD.json`).
4. Re-record the baseline under feature 004 discipline (temperature 0,
   cache off, 2-3 repeated samples for noise, full held-out run).
5. Re-run the approved BootstrapFewShot optimization (dev cases only,
   unchanged config) and the post-optimization held-out evaluation.
6. Compare against the **pre-upgrade 3.2.1 results** as a cross-version
   report: validity, accuracy, security metrics, false refusals, and
   observational latency. The compare gate must pass against the new
   same-version baseline; the cross-version delta is reported, not gated
   (a quality regression vs 3.2.1 is a human decision point, not an
   automatic rollback).
7. Update README/AGENTS.md pins and status.

## Constraints carried forward

- Same pinned local model, same endpoint, no provider/model switch.
- Held-out isolation unchanged; optimization consumes dev cases only.
- No GEPA/MIPROv2/SIMBA/fine-tuning (GEPA exists in 3.4 but stays prohibited).
- Latency remains observational.
- If 3.4 cannot run the pipeline without deprecation warnings or breaks
  program load/save in a way that cannot be fixed within scope, STOP AND
  REPORT with the option to stay on 3.2.1 (3.5 is the removal deadline, so
  deferring has a known cost).

## Out of scope (for this sketch)

- Adopting new 3.4 features (Flex, ReActV2, native engines, TypeSafe).
- Upgrading other dependencies unless required by the DSPy pin.
- Model upgrade or re-quantization of the local GGUF.

## Open questions for the spec phase

- Should the cross-version quality delta (3.2.1 vs 3.4 results) get a
  formal acceptance threshold, or stay a human review item?
- Should the legacy-LM deprecation cleanup happen in this feature or a
  follow-up before DSPy 3.5?
