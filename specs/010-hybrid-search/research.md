# Phase 0 Research: Hybrid Search over Ticket Texts

**Feature**: 010-hybrid-search | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

All design unknowns from the plan's Technical Context are resolved below.
Each entry: Decision / Rationale / Alternatives considered. Grounding:
`app/ai/llm.py` (pinned-endpoint discipline), `app/data/graphjin_client.py`
(the existing single DB path), `app/security/validator.py` (deterministic
validation), `scripts/import_dataset.py` (atomic import), `database/roles.sql`
(read-only role), feature 009 (text artifact + generator discipline), and a
live probe of `pgvector/pgvector:pg16` (pgvector 0.8.7) verifying the exact
SQL shapes used below.

## R1 — Retrieval channel: governed app-layer read-only channel (not GraphJin)

**Decision**: Retrieval runs through a NEW governed read-only channel in the
application layer (`app/ai/retrieval.py`), NOT through GraphJin. The channel
connects as the existing `itsm_readonly` role and issues a small, fixed set
of parameterized SQL statements (lexical ts_rank, semantic cosine, RRF
fusion) built by code — never by the model — over an explicit allowlist of
the three generated text fields. It enforces a result limit and returns a
sanitized retrieval trace.

**Rationale**: Human decision 1. GraphJin v3 is a structured-query boundary;
its built-in "discovery semantic search" is catalog-level (it embeds schema
metadata so GraphJin's internal agent finds *which tables/columns* to use),
not row-level content retrieval, so it cannot answer "tickets about login
problems" over the ticket texts (spec Background, evaluated and rejected
2026-10-13). Ranked hybrid retrieval is a different query shape than
GraphJin expresses. Duplicating the governance guarantees (allowlist, limit,
read-only role, sanitized trace) in the app layer is explicit and testable.

**Alternatives considered**: (a) Retrieval through GraphJin — rejected:
cannot express ts_rank / vector cosine / RRF over row content. (b) Give the
model a SQL tool — rejected: forbidden by AGENTS.md. (c) A separate search
service (Elasticsearch/OpenSearch/vector DB) — rejected: new infra,
violates the "zero new services" preference; PostgreSQL already provides
both tsvector and pgvector.

## R2 — Embedding model + endpoint

**Decision**: EmbeddingGemma-2 (Google, Apache 2.0), pinned
`ggml-org/embeddinggemma-2-GGUF`, Q8_0 quantization, served by a SEPARATE
pinned llama.cpp instance started with `--embeddings`. The chat server
(Qwen3) is untouched. Verified live on 2026-10-13: exact model ID
`models\embeddinggemma-2-Q8_0.gguf`, dimension 768, deterministic
(identical input -> identical vector, cosine 1.0), semantically sensible
(login~auth/SSO 0.79 > login~payment 0.60). Recorded in
`artifacts/embedding-preflight.json`.

**Rationale**: Human decision 2. EmbeddingGemma-2 is a dedicated embedding
model (contrastively trained), unlike the chat Qwen3, whose pooled hidden
states are not calibrated for semantic similarity. A separate pinned
instance keeps the two models' lifecycles independent and leaves the pinned
chat configuration untouched. Same preflight discipline as the main LLM:
`GET /v1/models` -> exact model ID -> deterministic smoke request -> record.

**Alternatives considered**: (a) nomic-embed-text (the sketch's example) —
superseded by the human's EmbeddingGemma-2 choice (newer, official llama.cpp
GGUF, Apache 2.0, strong MTEB). (b) Restart the chat server with
`--embeddings` — rejected: would disturb the pinned chat configuration and
Qwen3 is not an embedding model anyway. (c) Hosted embedding API — rejected:
forbidden.

## R3 — Embedding scope and per-ticket vector assembly

**Decision**: ONE vector per ticket over the concatenation of
`short_description` + `description` + `resolution_notes`. For the 250 open
tickets `resolution_notes` is NULL and only the available fields are
concatenated (never a placeholder). Fields are joined with a single newline;
the exact separator is a recorded constant. The input to the embedding model
is built from the pinned `tickets_texts.jsonl` (joined to `tickets.csv` for
the open/closed NULL rule), never from free text or credentials.

**Rationale**: Human decision 3. One vector per ticket keeps storage,
indexing, and fusion simple (single semantic ranking per ticket) and matches
the "tickets about X" / "similar to ticket N" granularity. Concatenation is
deterministic and recorded. Using all three fields captures resolution
signal for closed tickets without penalizing open tickets (whose
resolution_notes legitimately do not exist).

**Alternatives considered**: (a) description only (the sketch's original
recommendation) — superseded by the human's decision to include
resolution_notes. (b) Separate vectors per field (multi-vector) — rejected:
explicitly out of scope; adds fusion complexity for no measured benefit at
this corpus size. (c) Embedding structured columns too — rejected: the
structured path already covers structured filtering; retrieval targets text
content.

## R4 — Embedding generation mechanics (offline, checkpointed, resumable)

**Decision**: `scripts/generate_embeddings.py` mirrors the feature 009
generator discipline. It verifies the endpoint and exact model ID
(preflight), reads the pinned text artifact, embeds tickets in pinned order,
and appends each accepted vector to an append-only JSONL checkpoint
(`artifacts/tickets_embeddings.checkpoint.jsonl`). Resume is the default
when a checkpoint exists; `--fresh` discards it explicitly. The final
artifact `data/raw/tickets_embeddings.jsonl` is written only after all 2057
vectors are accepted, then the checkpoint is deleted. Bounded retries per
ticket, then a loud non-zero exit. No repair, no fabrication, no skipping.

**Rationale**: Reuses the proven 009 pattern (append-only JSONL checkpoint
is crash-safe, auditable, dependency-free; write the pinned artifact only at
completion keeps the boundary crisp). Embeddings are one call per ticket
(2057 calls); batching multiple tickets per `/v1/embeddings` request is
allowed by the OpenAI API and may be used as a recorded constant, but
per-ticket acceptance keeps validation simple.

**Alternatives considered**: (a) Single full-corpus call — rejected: no
per-ticket validation, large blast radius. (b) Offset-only checkpoint —
rejected: loses accepted vectors, making "resume must not silently skip"
unverifiable. (c) SQLite state — rejected: opaque, unnecessary at 2057 rows.

## R5 — Embedding determinism and dimension validation

**Decision**: Every accepted vector must have dimension exactly 768 and
finite numeric values; the generator asserts this per ticket. Determinism is
verified at preflight (identical input -> identical vector) and the manifest
records the dimension, quantization, and source GGUF SHA-256. Governance is
via pinning + validation + checksums; cross-environment bit-reproducibility
is NOT claimed (spec Assumptions).

**Rationale**: Dimension validity is the critical integrity check (a
wrong-dimension vector would corrupt the pgvector column). Determinism at a
fixed configuration is verified empirically (preflight cosine 1.0).

**Alternatives considered**: Claiming full byte-reproducibility across
hardware — rejected: not guaranteed and explicitly disclaimed by the spec.

## R6 — pgvector storage and indexing

**Decision**: Switch the pinned PostgreSQL image to `pgvector/pgvector:pg16`
(verified: PostgreSQL 16.15, pgvector 0.8.7). `itsm.tickets` gains an
`embedding vector(768)` column (additive, marked generated). A HNSW index is
created with cosine operator class:
`CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`. Similarity uses
the `<=>` cosine distance operator. `CREATE EXTENSION vector` is added to
the idempotent schema.

**Rationale**: Human decision 8. pgvector is the zero-new-service way to get
vector search inside the existing PostgreSQL. HNSW gives approximate
nearest-neighbor search at this scale with good recall; cosine distance
matches EmbeddingGemma's normalized embedding space. All shapes verified
live against `pgvector/pgvector:pg16`.

**Alternatives considered**: (a) Keep `postgres:16.10-alpine` and install
pgvector as a package — rejected: the stock Alpine image has no `vector`
extension (verified: 61 available extensions, none `vector`); a pinned
purpose-built image is cleaner and reproducible. (b) IVFFlat index —
rejected: HNSW generally has better recall/latency and needs no training
data at build time. (c) Exact (no index) search — acceptable at 2057 rows
but HNSW is cheap and future-proof; both verified.

## R7 — Lexical full-text search (tsvector + ts_rank + GIN)

**Decision**: `itsm.tickets` gains a generated `tsvector` column over the
text fields with a GIN index:
`GENERATED ALWAYS AS (to_tsvector('english', coalesce(short_description,'')
|| ' ' || coalesce(description,'') || ' ' || coalesce(resolution_notes,'')))
STORED`, indexed `USING GIN`. Lexical ranking uses
`ts_rank(fts, plainto_tsquery('english', $query))` with
`WHERE fts @@ plainto_tsquery('english', $query)`. The query string is a
bound parameter — never interpolated — so no arbitrary SQL is possible.

**Rationale**: tsvector/ts_rank are built into PostgreSQL (zero new infra on
the lexical side) and verified working. A generated STORED column keeps the
index expression and the query expression consistent. `plainto_tsquery`
treats the input as plain text (safe for natural-language questions) and the
English configuration matches the English-only texts (feature 009).

**Alternatives considered**: (a) `to_tsquery` with operator syntax —
rejected: requires escaping/validation of user input and can error on
natural-language questions; `plainto_tsquery` is the safe choice. (b)
`pg_trgm` similarity — rejected: ts_rank over tsvector is the standard
lexical relevance signal and pairs cleanly with RRF. (c) Per-field tsvector
columns — rejected: one combined column matches the one-vector-per-ticket
semantic side.

## R8 — Deterministic fusion: RRF k=60 in the application layer

**Decision**: Lexical and semantic rankings are fused with Reciprocal Rank
Fusion, constant k=60, computed deterministically. Each side produces a
ranked list of ticket_ids; a ticket's fused score is
`sum over sides of 1/(60 + rank)`, with rank assigned by `ROW_NUMBER() OVER
(ORDER BY <side score> DESC)`; missing on a side contributes 0. The final
ordering is by fused score DESC with a deterministic tie-break on ticket_id
ASC. Identical inputs produce identical rankings (verified live).

**Rationale**: Human decision 4. RRF is rank-based, so it is robust to the
incompatible score scales of ts_rank vs cosine distance (no normalization
needed). k=60 is the standard constant. Computing it in the application
layer (or a single fixed SQL statement) keeps it deterministic and testable;
the tie-break on ticket_id removes any ambiguity.

**Alternatives considered**: (a) Weighted sum of normalized scores —
rejected: requires score normalization between incompatible scales and a
tuned weight; RRF is parameter-light and robust. (b) Learned fusion —
rejected: non-deterministic and out of scope.

## R9 — Retrieval in the answer path (opt-in planner tool)

**Decision**: Retrieval is a separate governed tool the planner can call
(human decision 5). The planner's classification gains content-question
categories (e.g. "tickets about X", "similar to ticket N") that route to the
retrieval tool instead of the structured GraphJin path. The structured path
is untouched. The answer program grounds its answer on the retrieval result;
if retrieval returns no evidence, the answer path returns a stable
clarification/refusal (never fabricates). The retrieval trace (which
ticket_ids entered the context) is sanitized and attached.

**Rationale**: Opt-in keeps the proven structured path unchanged and makes
retrieval explicit per question type. Grounding on the retrieval result
satisfies FR-014 (no fabrication).

**Alternatives considered**: (a) Always run retrieval and augment grounding
— rejected: changes the structured path's behavior and cost for every
question. (b) A separate endpoint — rejected: unnecessary; the planner
already routes question types.

## R10 — Evaluation cases under isolation

**Decision**: Add +5 development retrieval cases to `evaluation/dev_cases.json`
and +8 held-out cases to `evaluation/cases.json` (including security
retrieval cases such as "retrieve tickets containing passwords/secrets" that
must return nothing prohibited). Files stay physically separate; case IDs
are stable and unique; zero held-out IDs are consumed by any tuning.
Retrieval quality is measured with real runs (temperature 0, cache disabled)
per feature 004 discipline.

**Rationale**: Human decision 6. Mirrors the existing dev/held-out/security
isolation (verified: dev=20, held-out=33, security=31 cases in separate
files). Security retrieval cases extend the feature 003 security discipline
to the new retrieval path.

**Alternatives considered**: Reusing existing structured cases — rejected:
they do not exercise retrieval. A single combined file — rejected: violates
physical separation.

## R11 — Image change and clean reset path

**Decision**: `compose.yml` pins `postgres` to `pgvector/pgvector:pg16`. The
documented clean reset path (`reset_database.py` -> `initialize_database.py`
-> `import_dataset.py`) rebuilds from the new image plus the pinned raw data
and the approved embedding artifact. No in-place migration of the existing
database is required (local demo dataset). `initialize_database.py` gains
idempotent `CREATE EXTENSION IF NOT EXISTS vector`, the vector column, and
the fts column + GIN index.

**Rationale**: Human decision 8. A pinned image change through the clean
reset path is reproducible and matches the project's "local demo dataset,
documented reset" assumption. Idempotent DDL keeps existing databases
convergent without forcing a reset.

**Alternatives considered**: In-place `CREATE EXTENSION` on the running
`postgres:16.10-alpine` — rejected: the extension is not present in that
image (verified), so it cannot be created there; the image must change.

## R12 — Test strategy (stubbed endpoint for unit, live for gated validation)

**Decision**: Unit tests stub the embedding endpoint (scripted HTTP
responses) and cover: vector dimension/schema acceptance and rejection,
checkpoint write/resume (simulated interruption -> resume -> exactly-once
coverage), RRF determinism and tie-break, allowlist enforcement, result-limit
enforcement, and tsvector query construction (asserting no arbitrary SQL is
built). Integration tests cover import (atomicity, idempotency, manifest
extension), end-to-end retrieval ("tickets about login problems" returns
relevant Account Access tickets; "similar to ticket 847203" returns
same-category tickets; the retrieval trace lists exactly the records that
entered the context), and security (write rejection, security retrieval
cases return nothing prohibited, trace hygiene). The REAL embedding run and
the REAL retrieval evaluation are quickstart/validation procedures whose
outputs are committed and then verified by deterministic tests — not pytest
live tests.

**Rationale**: AGENTS.md forbids simulated results for shipped artifacts but
stubbed-endpoint unit tests are standard for logic; keeping the 2057-call
live run and the live retrieval evaluation out of pytest keeps the 500-test
suite fast and hermetic.

**Alternatives considered**: Live-endpoint pytest tests as default —
rejected: endpoint availability would gate unrelated CI; live runs are part
of quickstart validation instead.
