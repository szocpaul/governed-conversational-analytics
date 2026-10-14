# Implementation Plan: Count over Content

**Branch**: `[012-count-over-content]` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-count-over-content/spec.md`

## Summary

Answer "how many tickets about X" (count-over-content) with a TRUE count of
matching tickets, via a governed, read-only, deterministic HYBRID count
query: a ticket counts as a match when it matches lexically
(`fts @@ plainto_tsquery`) OR semantically (vector distance <= a calibrated
threshold). This closes the gap where the structured path returns a
misleading 0 (the topic lives in the text, not a structured column) and the
content path returns a list capped at 25 (which would undercount). The count
is a true total (never limited by the retrieval cap), grounded with up to 5
example ticket_ids in a sanitized trace. Count-over-content questions are
routed via a new `content_count` category in the feature 011 classifier; the
structured and content paths are unchanged. The semantic threshold is
calibrated on dev cases only and measured on held-out cases per feature 004
discipline; if calibration cannot reach the count-accuracy threshold, the
run stops and reports to the human.

Primary requirement sources: spec.md FR-001..FR-012, SC-001..SC-009, and the
six binding human decisions recorded in the spec's Background section.

## Technical Context

**Language/Version**: Python 3.14.4 (project interpreter)

**Primary Dependencies**: dspy==3.4.0 (lm15 engine, BootstrapFewShot for any
classifier tuning), pydantic==2.12.5, httpx==0.28.1, psycopg==3.3.6,
pytest==9.0.3 — all already pinned; no new third-party dependencies. The
pinned EmbeddingGemma-2 endpoint embeds the count query text (same as
retrieval); the pinned Qwen3 chat model performs classification.

**Storage**: PostgreSQL via the pinned `pgvector/pgvector:pg16` image (the
feature 010 `fts` tsvector + GIN index and `embedding vector(768)` + HNSW
index are reused for the hybrid count); the calibrated threshold as a
versioned parameter recorded in a pinned artifact; evaluation corpora as
versioned JSON.

**Testing**: pytest (622 pre-existing tests must stay green); new unit tests
(count query construction, allowlist enforcement, threshold validation,
routing of count-over-content) and integration tests (true count, paraphrase
count, no undercount, structured unchanged, security count cases) in the
existing tests/unit + tests/integration layout.

**Target Platform**: Linux host with Docker Compose stack (PostgreSQL +
GraphJin) and network access to the local llama.cpp endpoints (chat +
embedding) via Tailscale.

**Project Type**: Retrieval/count feature for an existing web-service
project (a governed count query + a classifier category + evaluation).

**Performance Goals**: None as a gate (AGENTS.md: latency is observational
only). The count is a single governed query; latency is reported but never
gates.

**Constraints**: Local pinned endpoints only (exact model IDs, no fallback,
temperature 0, cache disabled); the count query is governed (field
allowlist, read-only role, parameterized, sanitized trace); the count is a
true total (never capped by the retrieval limit); the semantic threshold is
calibrated and recorded (never hardcoded); calibration consumes dev cases
only (zero held-out leakage); the structured and content paths are frozen;
no credentials, endpoint details, or prompts in output or traces; grouped
counts over content are out of scope; UI changes out of scope.

**Scale/Scope**: 1 governed count query (mirroring the retrieval channel), 1
classifier category addition + routing, threshold calibration, +5 dev / +6
held-out cases, ~10-12 tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`.specify/memory/constitution.md`) is an
unfilled template, so per AGENTS.md source-of-truth precedence the approved
spec plus AGENTS.md govern. Mapping of the relevant AGENTS.md prohibitions
to this design:

| AGENTS.md rule | How this plan complies |
|---|---|
| "DO NOT bypass GraphJin with direct arbitrary SQL from the model or application" | The count is a governed, allowlisted, read-only channel (same discipline as the feature 010 retrieval channel, human-approved): a fixed, parameterized COUNT query built by code, never by the model, over the allowlisted text fields. |
| "DO NOT give the model unrestricted database credentials" | The count connects as the existing `itsm_readonly` role only (SELECT, statement_timeout 5s). |
| "DO NOT switch to another model, hosted provider, or cloud fallback" | The count query text is embedded by the pinned EmbeddingGemma-2 endpoint; classification is the pinned Qwen3 model; no fallback. |
| "DO NOT simulate model, database, security, baseline, or evaluation results" | Count accuracy, the calibrated threshold, and the structured-regression check all come from real measured runs (temperature 0, cache disabled). |
| "DO NOT optimize on held-out evaluation cases" | Threshold calibration consumes development cases only; the held-out set is used only for evaluation; the leakage guard is unchanged. |
| "DO NOT run GEPA, MIPROv2, SIMBA, or fine-tuning" | The threshold is calibrated by a deterministic sweep over dev cases (not a forbidden optimizer); any classifier tuning uses only the approved bounded BootstrapFewShot. |
| "DO NOT use latency as a pass/fail quality gate" | Latency is observational only. |
| "DO NOT commit API keys, passwords, tokens, or generated secrets" | The threshold artifact and evaluation records contain parameters and hashes only; no secrets. |

No constitution/governance violations; Complexity Tracking is empty.

*Post-design re-check (after Phase 1)*: the design artifacts (research.md,
data-model.md, contracts/, quickstart.md) introduce no new conflicts with
the mapping above. Specifically: the count query is parameterized and
read-only (no arbitrary SQL); the threshold is calibrated on dev cases only
and recorded as a versioned parameter; the structured and content paths are
untouched; and no new dependencies, services, or secrets were introduced.
Gate still passes.

## Project Structure

### Documentation (this feature)

```text
specs/012-count-over-content/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── count-query.md
│   ├── routing.md
│   └── evaluation.md
├── checklists/
│   └── requirements.md  # From /speckit-specify (already validated)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/ai/
├── retrieval.py              # MODIFIED: add a governed hybrid COUNT query
│                             #      (lexical OR semantic-within-threshold)
│                             #      alongside the existing ranked-list query;
│                             #      same allowlist, read-only role,
│                             #      parameterized, sanitized trace.
├── routing.py                # MODIFIED: dispatch the content_count category
│                             #      to the count path.
└── signatures.py             # MODIFIED: ClassifyQuestion gains the
                              #      content_count category (docstring =
                              #      versioned instruction); PROMPT_VERSION bump.

app/api/
└── routes.py                 # MODIFIED: route content_count to the governed
                              #      count path; ground the answer on the count
                              #      plus up to 5 example ticket_ids.

app/ai/
└── count_calibration.py      # NEW: deterministic threshold calibration over
                              #      dev cases (a distance sweep, not a
                              #      forbidden optimizer); writes the versioned
                              #      threshold artifact.

data/raw/ or artifacts/
└── count-threshold.json      # NEW, COMMITTED: the calibrated, versioned
                              #      semantic-match threshold + provenance
                              #      (calibration dev IDs, method, created_at).

evaluation/
├── dev_cases.json            # MODIFIED: +5 count-over-content development cases.
├── cases.json                # MODIFIED: +6 held-out cases (incl. a security
│                             #      count case); physically separate from dev.
└── metrics.py                # MODIFIED: count-accuracy (exact match) +
                              #      false-count routing metrics.

artifacts/
├── baseline.json             # MODIFIED (regenerated): include count metrics
│                             #      (pre-012 preserved).
└── current.json              # MODIFIED (regenerated): held-out eval incl.
                              #      count metrics.

tests/
├── unit/
│   ├── test_count_query.py           # NEW (count SQL construction, allowlist,
│   │                                 #      threshold validation, no arb SQL)
│   └── test_count_routing.py         # NEW (content_count category routing,
│                                     #      conservative fallback)
└── integration/
    ├── test_count_over_content_e2e.py # NEW (true count, paraphrase count, no
    │                                  #      undercount, structured unchanged)
    └── test_count_eval.py            # NEW (count accuracy + false-count on
                                      #      held-out; security count cases)
```

**Structure Decision**: The feature extends the existing single-project
layout. The hybrid count query lives in `app/ai/retrieval.py` alongside the
ranked-list query (same governed channel, same guarantees). The classifier
category follows the feature 011 discipline. Threshold calibration is a
deterministic, dependency-free sweep in a small module. No new services, no
frontend changes.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — nothing to justify.
