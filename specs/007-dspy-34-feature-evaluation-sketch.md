# Feature Sketch: DSPy 3.4 Feature Evaluation (007)

**Status**: Evaluation COMPLETE (2026-10-11, research session, no code
changes). Four of five features rejected; one adopt candidate remains:
**explicit lm15 native-engine pin** (DSPy 3.5 readiness). This sketch now
scopes only that follow-up.
**Depends on**: specs 001-006 complete (006 delivered DSPy 3.4.0 with
re-baseline and re-optimization).

## Evaluation summary (2026-10-11)

Method: installed DSPy 3.4.0 source/docstring inspection, one live call
against the project's pinned endpoint with backend-selection
instrumentation, project usage grep (no tools, no async in the query path),
and governance constraints from AGENTS.md.

| Feature | Verdict | Key evidence |
|---|---|---|
| **lm15 / native engines** | **ADOPT candidate** (see scope below) | Live check: our `engine="auto"` config already resolves to the native lm15 backend (`native: True`, provider `openai-chat` / `OpenAIChatLM`) for the pinned llama.cpp endpoint. DSPy 3.5 removes the legacy path (`lm(messages=[...])`, custom `BaseLM.forward()`, `LegacyEngine`) — none used by the project directly, but the silent LiteLLM fallback under `auto` is unpinned behavior. |
| **ReActV2** | REJECT | Tool-using async agent; the project has zero tools by design (governed surface: planner emits typed JSON, deterministic validator is the boundary, GraphJin is the only data path). AGENTS.md prohibits giving the model an arbitrary SQL execution tool. Serving path is synchronous. Experimental status. |
| **Flex** | REJECT (under current governance) | Flex's purpose is GEPA rewriting module source (`module_src`); under BootstrapFewShot it is only a heavier Predict wrapper. GEPA is prohibited (AGENTS.md). Our metric is binary without feedback text — GEPA's reflective loop would be random search anyway. Experimental status. |
| **TypeSafe / Jev** | REJECT | Requires an external service (`TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, "System One API") — conflicts with "no provider switch" and private-endpoint hygiene. Decision types (Noul/Choice/Score) add probability evidence the project's discrete classification/planning outputs and evidence-grounding rule do not need. Experimental status. |
| **MCP support** | REJECT | `dspy.utils.mcp` converts MCP tools into DSPy tools — presupposes tool use (see ReActV2). Data access must stay behind the governed GraphJin boundary; MCP would introduce non-governed data sources. |

## Remaining scope: explicit lm15 pin (DSPy 3.5 readiness)

1. Pin `engine="lm15"` in `app/ai/llm.py` (`configure_dspy`) so the native
   backend is required, not silently selected: any future environment or
   DSPy change that would fall back to the LiteLLM compatibility engine
   fails loudly instead of changing the measured runtime.
2. Add a test asserting the resolved backend is native (lm15) for the
   configured LM — guards against silent fallback.
3. Re-run the standard validation gates (full test suite; the measured-run
   deprecation check from feature 006 must stay at zero DSPy warnings).
4. Baseline impact assessment: if the pin does not change measured behavior
   (expected — `auto` already resolves native), a full re-baseline is NOT
   required; record the verification runs in the feature's notes. If any
   measured difference appears, STOP AND REPORT and apply feature 004
   baseline discipline.
5. Update README/AGENTS.md pins if the change lands.

## Constraints carried forward

- Same pinned local model and endpoint; no provider/model switch.
- No other DSPy 3.4 feature adoption (see verdicts above).
- Held-out isolation, approved-optimizer rule, and latency-observational
  rules unchanged.
- If `engine="lm15"` breaks the pipeline on the pinned endpoint (e.g. a
  client setting the native engine cannot honor), STOP AND REPORT with the
  option to stay on `auto` and revisit before the DSPy 3.5 upgrade.

## Out of scope

- Migrating to explicit `dspy.lm15.Request`/`Response` calls at call sites
  (the adapters handle this on the native path; revisit only if DSPy 3.5
  deprecates more surface).
- `register_provider` declaration for the local endpoint (only needed if the
  model string stops resolving natively; current resolution works).
- Re-evaluating Flex if the GEPA prohibition is ever lifted (would need its
  own governance decision first).

## Open questions for the spec phase

- None blocking. Default assumption: the pin is behavior-preserving; the
  spec phase should confirm this with one measured sample before deciding
  the baseline question (scope item 4).
