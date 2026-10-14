# Implementation Plan: Classifier-Based Content Routing

**Branch**: `[011-classifier-content-routing]` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-classifier-content-routing/spec.md`

## Summary

Replace the narrow regex-based content-question router with a tuned,
meaning-based DSPy classifier so deep paraphrase content questions reach
governed hybrid retrieval. The existing `ClassifyQuestion` signature gains
`content_about` and `content_similar` categories so ONE classifier routes
every question (structured / content / ambiguous / unsupported); the
deterministic regex pair (`_ABOUT_RE`, `_SIMILAR_RE`, `_route_content_question`)
is removed. For content_similar, a deterministic extractor pulls the
reference ticket_id from the question; the classifier decides the mode only.
Routing is conservative: uncertainty defaults to the structured path. The
classifier is tuned with BootstrapFewShot (the only AGENTS.md-approved
optimizer) on new labeled development routing cases only, measured on a
held-out routing set with a false-routing guard (structured questions must
not be mis-routed to retrieval, and the structured execution-accuracy gate
must not regress). If BootstrapFewShot does not reach the calibrated
routing-accuracy threshold, the run stops and reports to the human.

Primary requirement sources: spec.md FR-001..FR-013, SC-001..SC-008, and the
seven binding human decisions recorded in the spec's Background section.

## Technical Context

**Language/Version**: Python 3.14.4 (project interpreter)

**Primary Dependencies**: dspy==3.4.0 (lm15 engine, BootstrapFewShot),
pydantic==2.12.5, httpx==0.28.1, psycopg==3.3.6, pytest==9.0.3 — all already
pinned; no new third-party dependencies. The pinned Qwen3 chat model performs
the classification; the pinned EmbeddingGemma-2 endpoint performs query
embedding for retrieval (both already in place from features 002/010).

**Storage**: PostgreSQL via the pinned `pgvector/pgvector:pg16` image
(retrieval, unchanged); GraphJin 3.21.6 (structured path, unchanged); the
tuned classifier artifact as a versioned JSON file
(`app/ai/optimized_program.json`, extended with routing demos) plus the
optimization-run record (`artifacts/optimization-run.json`).

**Testing**: pytest (571 pre-existing tests must stay green); new unit tests
(classifier output parsing, deterministic ticket_id extraction, conservative
fallback, regex removal) and integration tests (deep paraphrase routing to
retrieval, structured routing unchanged, unsupported refusal, security
content cases) in the existing tests/unit + tests/integration layout.

**Target Platform**: Linux host with Docker Compose stack (PostgreSQL +
GraphJin) and network access to the local llama.cpp endpoints (chat +
embedding) via Tailscale.

**Project Type**: Classifier/routing feature for an existing web-service
project (a DSPy signature change + routing integration + evaluation).

**Performance Goals**: None as a gate (AGENTS.md: latency is observational
only). Decision 7 confirms routing adds NO extra model call (the existing
classifier call now also routes content). Latency is reported but never
gates.

**Constraints**: Local pinned endpoints only (exact model IDs, no fallback,
temperature 0, cache disabled); BootstrapFewShot is the ONLY approved
optimizer (GEPA/MIPROv2/SIMBA forbidden); tuning consumes development cases
only (zero held-out leakage); the retrieval motor (feature 010) and the
structured planner (PlanQuery) are frozen — only the routing decision
changes; conservative fallback to the structured path; no credentials,
endpoint details, or prompts in output or traces; UI changes out of scope.

**Scale/Scope**: 1 signature change (2 new categories), 1 deterministic
ticket_id extractor, routing integration in `app/api/routes.py`, +8 dev /
+10 held-out routing cases, 1 BootstrapFewShot tuning run, baseline +
held-out eval, ~10-15 tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`.specify/memory/constitution.md`) is an
unfilled template, so per AGENTS.md source-of-truth precedence the approved
spec plus AGENTS.md govern. Mapping of the relevant AGENTS.md prohibitions
to this design:

| AGENTS.md rule | How this plan complies |
|---|---|
| "DO NOT run GEPA, MIPROv2, SIMBA, or fine-tuning" | Tuning uses ONLY the approved bounded BootstrapFewShot (the same `optimizer_config()` discipline as feature 004). If it does not reach the threshold, the run STOPS and reports to the human — no fallback to a forbidden optimizer. |
| "DO NOT optimize on held-out evaluation cases" | Tuning consumes development routing cases only; `assert_no_held_out_leakage` (feature 004) guards the trainset; the held-out routing set is used only for evaluation. |
| "DO NOT simulate model, database, security, baseline, or evaluation results" | Routing accuracy, false-routing rate, and the structured-regression check all come from real measured runs (temperature 0, cache disabled); unit tests stub the LM but shipped metrics never do. |
| "DO NOT switch to another model, hosted provider, or cloud fallback" | The classifier is the pinned Qwen3 chat model; retrieval query embedding is the pinned EmbeddingGemma-2 endpoint; no fallback. |
| "The model MUST NOT receive an arbitrary SQL execution tool" | The classifier only outputs a routing category; the governed paths (GraphJin structured, governed retrieval) are unchanged. |
| "DO NOT use latency as a pass/fail quality gate" | Latency is observational only; routing adds no extra model call (decision 7). |
| "DO NOT commit API keys, passwords, tokens, or generated secrets" | The tuned artifact and optimization-run record contain demos, config, and hashes only; no secrets. |
| "DO NOT tick, approve, bypass, or reinterpret any MANUAL GATE" | This feature has no MANUAL GATE; the stop-and-report on insufficient tuning is a human decision point, not an agent-tickable gate. |

No constitution/governance violations; Complexity Tracking is empty.

*Post-design re-check (after Phase 1)*: the design artifacts (research.md,
data-model.md, contracts/, quickstart.md) introduce no new conflicts with
the mapping above. Specifically: tuning is dev-only with the leakage guard;
the regex removal does not weaken the deterministic security boundaries
(the validator, GraphJin policy, and the read-only role are untouched);
the conservative fallback cannot produce a wrong structured answer (it only
ever routes MORE conservatively); and no new dependencies, services, or
secrets were introduced. Gate still passes.

## Project Structure

### Documentation (this feature)

```text
specs/011-classifier-content-routing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── classifier-signature.md
│   ├── routing-integration.md
│   └── evaluation.md
├── checklists/
│   └── requirements.md  # From /speckit-specify (already validated)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/ai/
├── signatures.py             # MODIFIED: ClassifyQuestion gains content_about /
│                             #      content_similar categories (docstring =
│                             #      versioned instruction); PROMPT_VERSION bump.
├── query_program.py          # MODIFIED: route content categories to the
│                             #      governed retrieval path instead of the
│                             #      structured planner; conservative fallback.
├── optimization.py           # MODIFIED: a routing metric (correct category =
│                             #      1.0 else 0.0) alongside text_to_query_metric;
│                             #      trainset builder for routing dev cases.
└── optimized_program.json    # MODIFIED (regenerated): tuned classifier with
                              #      routing demos; pinned, SHA-256, provenance.

app/api/
└── routes.py                 # MODIFIED: remove _ABOUT_RE / _SIMILAR_RE /
                              #      _route_content_question; route via the tuned
                              #      classifier; deterministic ticket_id
                              #      extraction for content_similar.

app/ai/
└── routing.py                # NEW: deterministic ticket_id extractor + routing
                              #      category -> governed-path dispatch helpers
                              #      (pure functions, no LLM, no I/O).

evaluation/
├── dev_cases.json            # MODIFIED: +8 routing development cases.
├── cases.json                # MODIFIED: +10 held-out routing cases (incl.
│                             #      security); physically separate from dev.
└── metrics.py                # MODIFIED: routing-accuracy + false-routing
                              #      metrics for the held-out gate.

artifacts/
├── optimization-run.json     # MODIFIED (regenerated): routing tuning record
│                             #      (optimizer config, accepted demo IDs,
│                             #      artifact hash, versions).
├── baseline.json             # MODIFIED (regenerated): new baseline incl.
│                             #      routing metrics (pre-011 preserved).
└── current.json              # MODIFIED (regenerated): held-out eval incl.
                              #      routing metrics.

tests/
├── unit/
│   ├── test_routing_classifier.py    # NEW (stubbed LM: category parsing,
│   │                                 #      conservative fallback, content
│   │                                 #      categories route correctly)
│   └── test_ticket_id_extractor.py   # NEW (deterministic id extraction,
│                                     #      edge cases, no false positives)
└── integration/
    ├── test_content_routing_e2e.py   # NEW (deep paraphrase -> retrieval,
    │                                 #      structured unchanged, unsupported
    │                                 #      refused; live stack)
    └── test_routing_eval.py          # NEW (routing accuracy + false-routing
                                      #      on held-out; structured regression
                                      #      check; security content cases)
```

**Structure Decision**: The feature extends the existing single-project
layout. The classifier change follows the house discipline (typed signature,
docstring-as-instruction, PROMPT_VERSION). The deterministic ticket_id
extractor and routing dispatch live in a small pure-function module
(`app/ai/routing.py`) so they are unit-testable without an LLM. The tuning
reuses the feature 004 optimization discipline (bounded BootstrapFewShot,
leakage guard, pinned artifact). No new services, no frontend changes.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — nothing to justify.
