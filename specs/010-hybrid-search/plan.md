# Implementation Plan: Hybrid Search over Ticket Texts

**Branch**: `[010-hybrid-search]` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-hybrid-search/spec.md`

## Summary

Add governed hybrid search over the feature 009 ticket texts so content
questions ("tickets about login problems", "tickets similar to ticket
847203") return relevance-ranked, grounded results. A maintainer-run offline
pipeline embeds each ticket's text (`short_description` + `description` +
`resolution_notes`, the last absent for open tickets) into one
768-dimensional vector with the pinned local EmbeddingGemma-2 model (Q8_0)
on a separate pinned llama.cpp instance, checkpointed and resumable, with a
provenance manifest. The pinned PostgreSQL image switches to
`pgvector/pgvector:pg16`; the tickets table gains a vector column and a
generated full-text-search column with a GIN index, imported atomically. At
query time a new governed, read-only retrieval channel in the application
layer runs lexical (ts_rank) and semantic (pgvector cosine) ranking over an
explicit allowlist, fuses them deterministically (RRF, k=60), enforces the
result limit and read-only role, and returns a ranked set of ticket
references with a sanitized retrieval trace. Retrieval is a separate
governed tool the planner calls opt-in; the structured query path is
untouched. Retrieval quality is measured with real runs under feature 004
isolation discipline.

Primary requirement sources: spec.md FR-001..FR-020, SC-001..SC-010, and the
eight binding human decisions recorded in the spec's Background section.

## Technical Context

**Language/Version**: Python 3.14.4 (project interpreter)

**Primary Dependencies**: dspy==3.4.0 (lm15 engine), pydantic==2.12.5,
httpx==0.28.1, psycopg==3.3.6, pytest==9.0.3 — all already pinned. The
embedding model (EmbeddingGemma-2, Q8_0 GGUF) is served by a separate pinned
llama.cpp instance; no new Python runtime dependencies are introduced
(embedding calls use the existing httpx OpenAI-compatible client pattern;
vector SQL is written directly, no ORM).

**Storage**: PostgreSQL via the pinned `pgvector/pgvector:pg16` image
(pgvector 0.8.7 verified); GraphJin 3.21.6 (pinned) remains the governed
structured boundary (unchanged); generated artifacts as versioned JSONL +
JSON manifest files (`data/raw/tickets_embeddings.jsonl`,
`data/raw/embeddings-manifest.json`).

**Testing**: pytest (500 pre-existing tests must stay green); new unit tests
(embedding generator with a stubbed endpoint, RRF determinism, allowlist
enforcement, tsvector query construction, manifest schemas) and integration
tests (import, end-to-end retrieval, retrieval trace, write rejection,
security retrieval cases) in the existing tests/unit + tests/integration
layout.

**Target Platform**: Linux host with Docker Compose stack (PostgreSQL +
GraphJin) and network access to the local llama.cpp endpoints (chat +
embedding) via Tailscale.

**Project Type**: Data-pipeline + retrieval feature for an existing
web-service project (offline build-time embedder + database/import + a new
governed runtime retrieval channel).

**Performance Goals**: None as a gate (AGENTS.md: latency is observational
only). Embedding is a one-time offline run of 2057 calls; runtime is
recorded in the manifest for information only. Retrieval latency is reported
(per-request, median, p90, max) but never gates.

**Constraints**: Local pinned endpoints only (exact model IDs, no fallback,
temperature 0, cache disabled); pinned `data/raw/tickets.csv` and
`data/raw/tickets_texts.jsonl` byte-identical; embedding generation is
offline and never part of the runtime query path; embedding artifact
pinned/immutable once human-approved; import atomic + idempotent; retrieval
read-only via the read-only role with an explicit field allowlist and result
limit; deterministic RRF k=60; no credentials, endpoint details, or prompts
in user-facing output or traces; UI changes out of scope.

**Scale/Scope**: 2057 tickets, one 768-dim vector each; 3 text fields per
ticket; ~2057 embedding calls (or fewer with batching); ~20-25 new tests;
one new embedder CLI, one new retrieval module, modifications to
schema/import/roles, the planner/answer integration, and the evaluation
corpora.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`.specify/memory/constitution.md`) is an
unfilled template, so per AGENTS.md source-of-truth precedence the approved
spec plus AGENTS.md govern. Mapping of the relevant AGENTS.md prohibitions
to this design:

| AGENTS.md rule | How this plan complies |
|---|---|
| "DO NOT bypass GraphJin with direct arbitrary SQL from the model or application" | Retrieval is a governed, allowlisted, read-only channel (human decision 1). The model never emits SQL; the application issues fixed, parameterized retrieval queries (ts_rank / cosine / RRF) over an explicit field allowlist — the same "deterministic validator, no arbitrary SQL" discipline as feature 003. GraphJin's catalog-level semantic search was evaluated and rejected (spec Background). |
| "DO NOT give the model unrestricted database credentials" | Retrieval connects as the existing `itsm_readonly` role only (SELECT, statement_timeout 5s); the owner role is used only by the offline import script. |
| "DO NOT make GraphJin or PostgreSQL writable for the runtime query path" | Retrieval is read-only; write rejection is verified by tests; the read-only role's REVOKE grants are unchanged. |
| "DO NOT switch to another model, hosted provider, or cloud fallback" | Both the chat model and the embedding model are local, pinned, verified via `GET /v1/models` before any run; any mismatch is a loud stop. No hosted embedding API. |
| "DO NOT simulate model, database, security, baseline, or evaluation results" | The embedding artifact and all retrieval metrics come only from real recorded runs; unit tests stub the endpoint but shipped artifacts/metrics never do. |
| "DO NOT optimize on held-out evaluation cases" | New dev (+5) and held-out (+8) retrieval cases live in physically separate files; zero held-out IDs consumed by any tuning (feature 004 discipline). |
| "DO NOT silently generate replacement dataset records" / raw data immutable | `tickets.csv` and `tickets_texts.jsonl` stay byte-identical; embeddings are additive; the artifact is pinned, checksummed, and human-approved before import. |
| "The model MUST NOT receive an arbitrary SQL execution tool" | The planner gains a governed retrieval tool with a fixed, typed request shape — not a SQL tool. |
| "DO NOT commit API keys, passwords, tokens, or generated secrets" | Manifests record hashes and non-secret metadata only; `.env` discipline unchanged; the private endpoint is never exposed in UI, errors, or traces. |
| "DO NOT use latency as a pass/fail quality gate" | Retrieval latency is observational only. |

No constitution/governance violations; Complexity Tracking is empty.

*Post-design re-check (after Phase 1)*: the design artifacts (research.md,
data-model.md, contracts/, quickstart.md) introduce no new conflicts with
the mapping above. Specifically: the embedder never touches the database
(writes stay in the owner-role import script); the retrieval channel issues
only fixed parameterized queries as the read-only role; the retrieval trace
carries no credentials/endpoints/prompts; the image change to
`pgvector/pgvector:pg16` is a build-time change applied through the clean
reset path; and no new Python dependencies, hosted services, or secrets were
introduced. Gate still passes.

## Project Structure

### Documentation (this feature)

```text
specs/010-hybrid-search/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── embedder-cli.md
│   ├── retrieval-api.md
│   ├── artifact-schemas.md
│   └── database-schema.md
├── checklists/
│   └── requirements.md  # From /speckit-specify (already validated)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/ai/
├── embeddings.py             # NEW: embedding client + per-ticket vector
│                             #      assembly (typed, pydantic-validated);
│                             #      offline use only; not imported by the
│                             #      runtime query path hot loop.
└── retrieval.py              # NEW: governed hybrid retrieval — lexical
                              #      ts_rank + semantic pgvector cosine +
                              #      deterministic RRF (k=60) fusion, field
                              #      allowlist, result limit, read-only role,
                              #      sanitized retrieval trace.

app/api/
├── routes.py                 # MODIFIED: integrate the retrieval tool into the
│                             #      query path (opt-in per question type) with
│                             #      a sanitized retrieval trace.
└── schemas.py                # MODIFIED: typed retrieval request/response and
                              #      retrieval-trace event shapes.

scripts/
├── generate_embeddings.py    # NEW: embedding CLI — endpoint/model preflight,
│                             #      per-ticket embedding, JSONL checkpoint +
│                             #      resume, bounded retries, artifact +
│                             #      embeddings-manifest.json writing.
├── import_dataset.py         # MODIFIED: also load tickets_embeddings.jsonl,
│                             #      verify checksum + provenance, upsert the
│                             #      vector column in the same transaction,
│                             #      extend artifacts/import-manifest.json.
└── initialize_database.py    # MODIFIED: create the vector extension, vector
                              #      column, fts generated column + GIN index
                              #      (idempotent).

database/
└── schema.sql                # MODIFIED: itsm.tickets gains embedding
                              #      vector(768) + a generated fts tsvector
                              #      column + GIN index (additive, marked
                              #      generated); CREATE EXTENSION vector.

compose.yml                   # MODIFIED: postgres image pinned to
                              #      pgvector/pgvector:pg16 (provides the
                              #      vector extension).

data/raw/
├── tickets.csv               # UNCHANGED, pinned, byte-identical.
├── tickets_texts.jsonl       # UNCHANGED, pinned (feature 009), byte-identical.
├── tickets_embeddings.jsonl  # NEW, COMMITTED after approval: pinned embedding
│                             #      artifact (1 JSON object per line).
└── embeddings-manifest.json  # NEW, COMMITTED: provenance manifest (model ID,
                              #      quantization, dimension, source GGUF +
                              #      SHA-256, hashes, row count, created_at).

evaluation/
├── dev_cases.json            # MODIFIED: +5 retrieval development cases.
└── cases.json                # MODIFIED: +8 held-out cases (incl. security
                              #      retrieval cases); physically separate from
                              #      dev; zero held-out leakage into tuning.

artifacts/
├── import-manifest.json      # MODIFIED (additive): new top-level
│                             #      "ticket_embeddings" key; existing keys
│                             #      untouched.
└── embedding-preflight.json  # NEW (this plan's input): live embedding-endpoint
                              #      preflight evidence (model ID, dimension,
                              #      determinism, semantic sanity).

tests/
├── unit/
│   ├── test_embeddings_program.py        # NEW (stubbed endpoint, dim/schema)
│   ├── test_embeddings_checkpoint.py     # NEW (resume semantics)
│   ├── test_rrf_fusion.py                # NEW (determinism, k=60, ranking)
│   └── test_retrieval_allowlist.py       # NEW (allowlist + limit + tsvector
│                                         #      query construction, no arb SQL)
└── integration/
    ├── test_embeddings_import.py         # NEW (atomic import, idempotency,
    │                                     #      manifest extension)
    ├── test_retrieval_e2e.py             # NEW ("tickets about login",
    │                                     #      "similar to ticket N", trace)
    └── test_retrieval_security.py        # NEW (write rejection, security
                                          #      retrieval cases, trace hygiene)
```

**Structure Decision**: The feature extends the existing single-project
layout. The offline embedder mirrors the feature 009 generator discipline
(testable module under `app/ai/`, thin CLI under `scripts/`). The runtime
retrieval channel is a new module under `app/ai/` that issues fixed,
parameterized queries as the read-only role — a deliberate, governed
exception to "GraphJin is the only database path", approved by human
decision 1 because GraphJin's semantic search is catalog-level, not
row-level. The embedding artifact is committed under `data/raw/` next to the
pinned inputs because it is itself pinned, versioned, and human-approved.
The planner/answer integration reuses the existing opt-in tool pattern. No
frontend changes (human decision 7).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — nothing to justify. The one deliberate design choice that
could read as a rule tension (a second database access path alongside
GraphJin) is an explicit, human-approved, governed read-only channel with
the same guarantees, documented in research.md R1 and the Constitution Check
above — not a violation.
