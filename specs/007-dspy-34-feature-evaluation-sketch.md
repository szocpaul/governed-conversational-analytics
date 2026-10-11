# Feature Sketch: DSPy 3.4 Feature Evaluation (007)

**Status**: Sketch — not yet a full spec. Deferred from feature 006
(`specs/006-dspy-upgrade-sketch.md` / `specs/006-dspy-34-upgrade/`), whose
scope explicitly excluded adopting new DSPy 3.4 features.
**Depends on**: specs 001-006 complete (006 delivers the DSPy 3.4.0 runtime
with re-baseline and re-optimization).

## Origin

DSPy 3.4.0 ships new capabilities that feature 006 deliberately did not
adopt, to keep the version upgrade isolated and measurable. The user
requested that these be evaluated for usefulness to this project in a
follow-up spec:

- **Flex** (3.3.0+ experimental): code-optimizable modules — GEPA rewrites
  module source, not just instructions.
- **ReActV2** (3.4.0): async tool-using agent with `acall` and async tools.
- **Native LM engines / lm15** (3.4.0): `dspy.lm15` request/response/streaming
  types, `engine="auto"|"lm15"|"litellm"`, `register_provider` for custom
  OpenAI-compatible HTTP services. This one has a hard driver: DSPy 3.5
  removes the legacy LM path (`lm(messages=[...])` calls, custom
  `BaseLM.forward()` integrations, `LegacyEngine`). Feature 006 keeps the
  supported LiteLLM compatibility backend, so there is no emergency, but the
  migration question must be answered before 3.5.
- **TypeSafe / Jev** (3.4.0 experimental): decision types (`Noul`, `Choice`,
  `Score`) with probability evidence, `ReAnchor` calibration.
- **MCP support** (3.4.0): model-context-protocol tool integration.

## Proposed scope (evaluation, not adoption)

1. For each feature above, assess usefulness against this project's actual
   needs and governance constraints:
   - the governed read-only query surface (no arbitrary SQL; deterministic
     validator as boundary);
   - the pinned local llama.cpp model and endpoint (no provider switch);
   - the approved BootstrapFewShot-only optimizer rule (GEPA/MIPROv2/SIMBA
     prohibited — note: Flex is designed around GEPA, so its evaluation must
     respect or explicitly challenge that governance constraint);
   - baseline discipline (any adoption implies re-baseline).
2. Produce a written evaluation per feature: what it would enable, what it
   would cost (migration, new risks, governance conflicts), and a
   recommendation (adopt in a follow-up implementation spec / defer /
   reject).
3. The lm15/native-engine evaluation has priority because of the DSPy 3.5
   removal deadline; its recommendation should include a concrete migration
   plan sketch if adoption is recommended.
4. Any actual adoption is a separate implementation feature with its own
   spec, baseline, and gates — this feature produces evaluations and
   recommendations only.

## Constraints carried forward

- No code changes to the governed query path in this feature (evaluation
  only); experiments, if any, run outside the production path and never on
  held-out cases.
- Held-out isolation and the approved-optimizer rule remain in force.
- No provider/model switch; experiments use the same pinned local endpoint.

## Open questions for the spec phase

- Does the evaluation need runnable micro-benchmarks (e.g. lm15 vs LiteLLM
  latency/behavior on the local endpoint), or is a documented
  design-level assessment enough?
- Should the Flex evaluation be scoped given that its optimizer (GEPA) is
  prohibited by governance — evaluate Flex only under BootstrapFewShot, or
  formally request a governance exception as part of the recommendation?
