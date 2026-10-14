# Feature Specification: Hybrid Search over Ticket Texts

**Feature Branch**: `[010-hybrid-search]`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Add governed hybrid search (lexical full-text + semantic vector retrieval with deterministic fusion) over the synthetic ticket texts delivered by feature 009, so natural-language questions such as 'tickets about login problems' or 'tickets similar to ticket 847203' return relevance-ranked, grounded results through a read-only, allowlisted, audited retrieval path with the same governance guarantees as the existing structured query boundary. Retrieval is a separate governed tool the planner can call (opt-in per question type), leaving the existing structured query path untouched. Embeddings are produced offline by a pinned local embedding model (EmbeddingGemma-2, Q8_0 GGUF) on a separate pinned llama.cpp instance, with the same pinning, provenance, and no-fallback discipline as the main LLM. See specs/010-hybrid-search-sketch.md and the eight human-approved decisions of 2026-10-13."

## Background

Feature 009 delivered the text foundation: every ticket now has `short_description`, `description`, and `resolution_notes` (the latter SQL NULL for the 250 open tickets), generated, pinned, and exposed read-only. The existing conversational pipeline (features 002-005) answers *structured* analytical questions (counts, aggregates, breakdowns) through a governed GraphJin boundary, but has **no way to search the content of the text fields**. This feature adds that capability as a **governed hybrid retrieval** path with the same guarantees as the existing boundary: explicit allowlist of searchable fields, result limit, read-only database role, and a sanitized retrieval trace listing exactly which records entered the model's context.

Verified ground truths (checked directly on 2026-10-13 against the pinned data, the running services, and the live endpoints):

- 2057 tickets, 250 open (`closed_at` empty) / 1807 closed, 5 categories, 20 category x sub_category pairs, priorities P1-P4.
- `data/raw/tickets_texts.jsonl` is pinned (2057 rows, SHA-256 in `data/raw/texts-manifest.json`, human-approved).
- PostgreSQL full-text search (`tsvector`/`ts_rank`) is built into the pinned `postgres:16.10-alpine` image and works (sanity query verified).
- The `vector` extension (pgvector) is **not** present in the pinned `postgres:16.10-alpine` image (61 available extensions, none named `vector`); enabling it requires a pinned image change.
- The main chat endpoint does **not** support embeddings (`POST /v1/embeddings` returns 501; the loaded Qwen model is completion-only). A **separate pinned llama.cpp instance** running EmbeddingGemma-2 with `--embeddings` was verified on 2026-10-13: exact model ID `models\embeddinggemma-2-Q8_0.gguf`, embedding dimension **768**, deterministic (identical input -> identical vector), and semantically sensible (related phrases score higher than unrelated). Recorded in `artifacts/embedding-preflight.json`.
- Full pre-existing automated test suite: **500 tests**, green.

Human-approved decisions (binding, 2026-10-13):

1. **Retrieval channel**: a **separate governed read-only channel in the application layer** (not through GraphJin), duplicating the governance guarantees — explicit allowlist, result limit, read-only database role, sanitized trace. GraphJin's built-in semantic search is catalog-level (it finds *which tables/columns* to use), not row-level content retrieval, so it cannot answer "tickets about X" and was evaluated and rejected.
2. **Embedding model + endpoint**: **EmbeddingGemma-2** (Google, Apache 2.0), pinned `ggml-org/embeddinggemma-2-GGUF`, **Q8_0** quantization, on a **separate pinned llama.cpp instance** started with `--embeddings`; the chat server (Qwen3) is untouched. Same preflight discipline as the main LLM; no hosted API, no fallback.
3. **Embedding scope**: **one vector per ticket** computed over `short_description` + `description` + `resolution_notes` (concatenated); for the 250 open tickets `resolution_notes` is NULL and only the available fields are used.
4. **Fusion**: **deterministic Reciprocal Rank Fusion (RRF)** with the standard constant **k=60**, computed in the application layer.
5. **Retrieval in the answer path**: retrieval is a **separate governed tool the planner can call** (opt-in per question type, e.g. "tickets about X", "similar to ticket N"); the existing structured query path is untouched.
6. **Evaluation**: new retrieval cases per feature 004 discipline — **+5 development cases and +8 held-out cases** (including security cases such as "retrieve tickets containing passwords"), in physically separate files, with zero held-out leakage into any tuning.
7. **UI**: **deferred** — this feature is backend-only; the 008 query-discovery gallery picks up text-search examples in a small follow-up.
8. **pgvector**: switch the pinned PostgreSQL image to **`pgvector/pgvector:pg16`** (a pinned, versioned image change) to obtain the `vector` extension; recorded in the manifest.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Governed offline embedding generation with provenance (Priority: P1)

A data maintainer runs an explicit offline embedding step: the pinned local EmbeddingGemma-2 model reads each ticket's text fields (`short_description`, `description`, `resolution_notes` — the last absent for open tickets) from the pinned feature 009 artifact and produces one 768-dimensional vector per ticket. The endpoint and exact model identity are verified before the run (same preflight discipline as the main LLM); the run is deterministic, checkpointed, and resumable; and a provenance manifest records exactly which model, quantization, dimension, and configuration produced the pinned, SHA-256-checksummed embedding artifact.

**Why this priority**: This is the foundation. Without a governed, auditable, reproducible embedding artifact, nothing downstream (vector storage, semantic retrieval, hybrid fusion) can be trusted. It mirrors the feature 009 text-generation discipline and delivers value even if Stories 2-4 are absent (a trustworthy pinned embedding artifact exists).

**Independent Test**: Run the embedding step (including one interrupted-and-resumed run) against the verified local embedding endpoint and verify the completed artifact covers all 2057 tickets exactly once, every vector has dimension 768, the run is deterministic, and the provenance manifest is complete. Delivers value standalone.

**Acceptance Scenarios**:

1. **Given** the pinned ticket-text artifact and a verified local embedding endpoint (exact pinned model ID, recorded quantization), **When** the embedding step runs, **Then** it produces exactly one 768-dimensional vector per ticket (2057 total), computed over `short_description` + `description` + `resolution_notes` (only the available fields for open tickets), and every vector passes dimension and validity checks before acceptance.
2. **Given** a run interrupted after some tickets, **When** the embedding step is restarted, **Then** it resumes from the last checkpoint — it never restarts from scratch and never silently skips tickets.
3. **Given** an endpoint or model mismatch at pre-flight (wrong model ID, endpoint unreachable, embeddings route unsupported), **When** the embedding step is considered, **Then** it stops and reports; no fallback model, hosted provider, or cloud service is used.
4. **Given** the completed artifact, **When** the provenance manifest is inspected, **Then** it records the exact API model ID, quantization, embedding dimension (768), source GGUF and its SHA-256, generator script hash, row count, output SHA-256, and creation timestamp.
5. **Given** an approved embedding artifact, **When** regeneration is decided (e.g., model or scope change), **Then** it is a full run producing a NEW artifact version with new checksums and an updated manifest; the previously approved artifact remains intact, and partial or silent regeneration never occurs.

---

### User Story 2 - Database storage of embeddings and lexical index with provenance (Priority: P2)

A data maintainer rebuilds the local database after the embedding artifact is approved: the tickets table gains a vector column for the per-ticket embedding and a generated full-text-search column with an index over the text fields, the pinned embedding artifact is imported atomically together with the pinned data, and the import records the embedding artifact's provenance. The pinned source columns remain byte-identical to the pinned raw data.

**Why this priority**: The embeddings and the lexical index only become queryable once they are in the database under the same atomic-import and provenance discipline as the pinned dataset. It depends on Story 1's approved artifact but is independently testable against the database.

**Independent Test**: Reset the database, run the import of the approved pinned embedding artifact, and verify the tickets table has a populated vector column for all 2057 rows (dimension 768), a working full-text-search column/index over the text fields, pinned column values match the pinned raw data exactly, and the import manifest references the embedding artifact's checksum and provenance.

**Acceptance Scenarios**:

1. **Given** a clean database reset and an approved pinned embedding artifact, **When** the import runs, **Then** the tickets table contains all 2057 tickets with the vector column populated (dimension 768) and the full-text-search column/index built over the text fields, and the import either completes fully or leaves no partial state (atomic).
2. **Given** the imported data, **When** pinned columns are compared against the pinned raw ticket records, **Then** they match exactly — the feature is additive only and never modifies pinned data.
3. **Given** a completed import, **When** the import runs again, **Then** the result is identical (idempotent) and the clean local reset path still works.
4. **Given** a completed import, **When** the import manifest is inspected, **Then** it references the embedding artifact's checksum and provenance manifest in addition to the existing pinned-data provenance.
5. **Given** the database, **When** the vector extension is inspected, **Then** it is provided by the pinned `pgvector/pgvector:pg16` image and the extension version is recorded.

---

### User Story 3 - Governed hybrid retrieval as a planner tool (Priority: P3)

An analyst asks a content question — "show me tickets about login problems" or "find tickets similar to ticket 847203" — and the planner calls the new governed retrieval tool. The tool runs lexical full-text ranking and semantic vector similarity over only the allowlisted text fields, fuses the two rankings deterministically (RRF, k=60), enforces the result limit and the read-only database role, and returns a ranked set of ticket references together with a sanitized retrieval trace listing exactly which records entered the model's context. The grounded answer is then produced from those results; if evidence is absent, a stable clarification or refusal is returned — never a fabricated answer.

**Why this priority**: This is the user-facing capability the feature exists for. It depends on Stories 1 and 2 (the embeddings and index must exist) but is independently testable through the governed retrieval tool and the answer path.

**Independent Test**: Through the conversational query path, ask "tickets about login problems" and verify relevant Account Access tickets are returned with a retrieval trace; ask "similar to ticket 847203" and verify same-category tickets are returned; verify the structured query path is unchanged; verify write attempts through the retrieval path are rejected with zero database changes.

**Acceptance Scenarios**:

1. **Given** the imported database, **When** a content question such as "tickets about login problems" is asked, **Then** the planner calls the retrieval tool, which returns a relevance-ranked set of matching tickets (semantic match: "login" ~ "authentication", "SSO", "password") with a sanitized retrieval trace.
2. **Given** the imported database, **When** a similarity question such as "find tickets similar to ticket 847203" is asked, **Then** the tool returns tickets ranked by vector similarity, favoring the same category.
3. **Given** the retrieval tool, **When** its configuration is inspected, **Then** the searchable fields are explicitly allowlisted (only the three generated text fields), a result limit is enforced, the read-only database role is used, and no arbitrary-SQL path is introduced.
4. **Given** the retrieval tool, **When** the same query runs twice, **Then** the fused ranking is identical (deterministic RRF, k=60).
5. **Given** a content question with no relevant tickets, **When** retrieval returns no evidence, **Then** the answer path returns a stable clarification or refusal and never fabricates an answer.
6. **Given** the existing structured query path, **When** a structured analytical question (e.g. "how many P1 tickets") is asked, **Then** it is answered exactly as before this feature — retrieval is opt-in and does not alter the structured path.

---

### User Story 4 - Evaluation of retrieval quality under dataset isolation (Priority: P4)

A maintainer measures retrieval quality with real runs under the feature 004 isolation discipline: new development cases (for any tuning) and new held-out cases (for evaluation only) are added in physically separate files, including security cases (e.g. "retrieve tickets containing passwords/secrets") that must return nothing prohibited. No held-out case is consumed by tuning, and retrieval quality is reported from measured runs, never simulated.

**Why this priority**: Retrieval quality must be measured, not assumed, and tuning must not leak held-out data. It depends on Story 3 (the retrieval path must exist) and closes the governance loop.

**Independent Test**: Add the new development and held-out retrieval cases in separate files; run the held-out evaluation with temperature zero and cache disabled; verify the security retrieval cases return nothing prohibited and no held-out ID appears in any tuning input.

**Acceptance Scenarios**:

1. **Given** the retrieval path, **When** the evaluation case files are inspected, **Then** new development cases (+5) and held-out cases (+8, including security retrieval cases) exist in physically separate files with stable unique IDs.
2. **Given** the held-out retrieval cases, **When** the evaluation runs (temperature zero, cache disabled), **Then** retrieval quality metrics are reported from real runs, and any security retrieval case returns nothing prohibited.
3. **Given** any retrieval tuning, **When** its inputs are inspected, **Then** zero held-out case IDs are consumed (isolation per feature 004 discipline).

---

### Edge Cases

- Embedding endpoint or model mismatch at pre-flight (wrong model ID, endpoint unreachable, embeddings route unsupported): the embedding step MUST stop and report; no fallback model, hosted provider, or cloud service may be used.
- An embedding response with the wrong dimension or an invalid vector: the entry MUST fail validation; the run MUST NOT fabricate, patch, or skip the affected ticket.
- Interruption mid-run (process killed, machine restart): the next run MUST resume from the last checkpoint and still produce exactly 2057 unique vectors — never a restart from scratch, never silently skipped tickets.
- An open ticket (`resolution_notes` NULL): its embedding MUST be computed from the available fields only (`short_description` + `description`); the NULL field is never replaced with placeholder text.
- A retrieval query that matches nothing: the tool MUST return an empty result set and the answer path MUST return a stable clarification or refusal — never a fabricated answer.
- A retrieval query attempting to search a non-allowlisted field: the allowlist MUST reject it.
- A write attempt through the retrieval path (INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER, DROP): MUST be rejected with zero database changes.
- A security retrieval query (e.g. "retrieve tickets containing passwords/secrets"): MUST return nothing prohibited, and the retrieval trace MUST contain no credentials, endpoint details, or prompts.
- The same retrieval query run twice: MUST produce an identical fused ranking (deterministic RRF).
- A model or scope change after approval: MUST produce a new artifact version with new checksums and an updated manifest; the previously approved artifact stays intact and pinned.
- Existing database with the old image: the documented clean reset path rebuilds from the pinned `pgvector/pgvector:pg16` image plus the pinned raw data and the approved embedding artifact; no in-place migration of production data is needed (local demo dataset only).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The embedding step MUST read only the pinned feature 009 ticket-text artifact as input; the pinned raw files and the pinned text artifact MUST remain byte-identical (verified by their recorded checksums) after embedding generation.
- **FR-002**: Embedding MUST use a pinned local EmbeddingGemma-2 model (exact pinned API model ID `models\embeddinggemma-2-Q8_0.gguf`, Q8_0 quantization, Apache 2.0) served by a separate pinned llama.cpp instance started with `--embeddings`; endpoint and model identity MUST be verified before the run (same pre-flight discipline as the main LLM); no fallback model, hosted provider, or cloud service may be used.
- **FR-003**: For each ticket the pipeline MUST produce exactly one embedding vector of dimension 768, computed over `short_description` + `description` + `resolution_notes` (only the available fields when `resolution_notes` is NULL for open tickets); every vector MUST pass dimension and validity checks before acceptance.
- **FR-004**: The embedding run MUST be deterministic (identical input produces identical vector), MUST checkpoint progress, and a restarted run MUST resume from the last checkpoint — never restart from scratch, never silently skip tickets; the completed run MUST cover every ticket exactly once (2057 of 2057).
- **FR-005**: The completed embedding artifact MUST be pinned, versioned, SHA-256-checksummed, and treated as immutable once human-approved — the same discipline as the project's baseline, optimized-program, and feature 009 text artifacts.
- **FR-006**: Regeneration MUST be a full run producing a new artifact version with new checksums and an updated manifest; partial or silent regeneration MUST NOT occur, and previously approved artifacts MUST remain intact.
- **FR-007**: A provenance manifest MUST record the exact API model ID, quantization, embedding dimension (768), source GGUF and its SHA-256, generator script hash, row count, output SHA-256, and creation timestamp; it MUST be stored with the embedding artifact and referenced from the import manifest.
- **FR-008**: The pinned PostgreSQL image MUST be changed to `pgvector/pgvector:pg16` (a pinned, versioned image) to provide the `vector` extension; the extension version MUST be recorded.
- **FR-009**: The tickets table MUST gain a vector column for the per-ticket embedding (dimension 768) and a generated full-text-search column with an index over the text fields; all pinned columns MUST keep their pinned values.
- **FR-010**: The database import MUST load the approved pinned embedding artifact atomically together with the pinned data (all 2057 rows), MUST be idempotent on re-run, and the clean local reset path MUST remain intact.
- **FR-011**: Retrieval MUST be exposed as a separate governed read-only channel in the application layer (not through GraphJin), duplicating the governance guarantees: an explicit allowlist of searchable fields (only the three generated text fields), an enforced result limit, use of the read-only database role, and a sanitized retrieval trace listing exactly which records entered the model's context.
- **FR-012**: Retrieval MUST combine lexical full-text ranking and semantic vector similarity and MUST fuse the two rankings deterministically using Reciprocal Rank Fusion with the standard constant k=60, computed in the application layer; identical queries MUST produce identical fused rankings.
- **FR-013**: Retrieval MUST be a separate governed tool the planner can call (opt-in per question type, e.g. "tickets about X", "similar to ticket N"); the existing structured query path MUST remain untouched and MUST answer structured analytical questions exactly as before.
- **FR-014**: A factual answer MUST be supported by the retrieval result; if evidence is absent, ambiguous, or unavailable, the answer path MUST return a stable clarification, refusal, or dependency error and MUST NOT fabricate an answer.
- **FR-015**: All write operations through the retrieval path (INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER, DROP) MUST be rejected with zero database changes, and no arbitrary-SQL path MUST be introduced.
- **FR-016**: The retrieval trace and any error response MUST NOT expose credentials, private endpoint details, complete prompts, or prohibited data.
- **FR-017**: New retrieval evaluation cases MUST be added under the feature 004 isolation discipline: at least 5 new development cases and at least 8 new held-out cases (including security retrieval cases) in physically separate files with stable unique IDs; zero held-out case IDs MUST be consumed by any tuning.
- **FR-018**: Retrieval quality MUST be measured with real runs (temperature zero, cache disabled); security retrieval cases MUST return nothing prohibited; results MUST NOT be simulated.
- **FR-019**: The feature MUST NOT regress existing behavior: the full pre-existing automated test suite (500 tests) MUST pass unchanged, and query behavior over the pre-existing governed columns MUST be unaffected.
- **FR-020**: UI changes MUST NOT be included in this feature; the query-discovery gallery text-search examples are deferred to a follow-up.

### Key Entities *(include if feature involves data)*

- **Ticket Embedding**: One 768-dimensional vector per ticket, produced by the pinned EmbeddingGemma-2 model from the ticket's text fields (`short_description` + `description` + `resolution_notes`; available fields only for open tickets). Stored as an additive column on the ticket record.
- **Embedding Artifact**: The pinned, versioned, SHA-256-checksummed output of one full recorded embedding run; immutable once human-approved.
- **Embedding Provenance Manifest**: The versioned record of how the embedding artifact was produced (exact model ID, quantization, dimension, source GGUF and its checksum, generator script hash, row count, output checksum, creation timestamp), enabling audit and full-version regeneration.
- **Retrieval Result**: A relevance-ranked set of ticket references produced by fusing lexical and semantic rankings, together with a sanitized retrieval trace listing exactly which records entered the model's context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Embedding artifact integrity: once human-approved, the embedding artifact is pinned and its recorded SHA-256 remains stable; any later change appears only as a new artifact version with new checksums and an updated manifest.
- **SC-002**: Embedding coverage and validity: the completed embedding artifact covers all 2057 tickets exactly once, and 100% of vectors have dimension 768 and pass validity checks.
- **SC-003**: Embedding determinism and resume: identical input produces identical vectors, and an interrupted run resumes from its checkpoint and completes with exactly 2057 unique vectors — zero restarts from scratch, zero silently skipped tickets.
- **SC-004**: Provenance completeness: the embedding provenance manifest contains the exact API model ID, quantization, dimension, source GGUF and its checksum, generator script hash, row count, output checksum, and creation timestamp, and the recorded checksums verify against the artifacts on disk.
- **SC-005**: Retrieval relevance: a measured run of "tickets about login problems" returns relevant Account Access tickets, and "similar to ticket 847203" returns same-category tickets, verified against the real database.
- **SC-006**: Retrieval determinism: identical retrieval queries produce identical fused rankings across repeated runs.
- **SC-007**: Governance: 100% of attempted write operations through the retrieval path are rejected with zero database changes; the searchable fields are limited to the explicit allowlist; the retrieval trace lists exactly the records that entered the context and contains no credentials, endpoint details, or prompts.
- **SC-008**: Security: 100% of security retrieval cases return nothing prohibited.
- **SC-009**: Evaluation isolation: new development and held-out retrieval cases exist in physically separate files, and zero held-out case IDs appear in any tuning input.
- **SC-010**: Zero regression: the full pre-existing automated test suite (500 tests) passes with no failures introduced by this feature, and structured analytical questions are answered exactly as before.

## Assumptions

- The eight human decisions of 2026-10-13 are binding: separate governed app-layer retrieval channel; EmbeddingGemma-2 (Q8_0) on a separate pinned llama.cpp instance; one vector per ticket over all three text fields; deterministic RRF k=60; retrieval as an opt-in planner tool; +5 dev / +8 held-out evaluation cases; UI deferred; pgvector via the pinned `pgvector/pgvector:pg16` image.
- The embedding generator is an offline build-time step run by a maintainer against the local embedding endpoint, not part of the runtime query path; it introduces no runtime dependency on the embedding endpoint at query time (embeddings are precomputed and stored).
- Embedding generation is not claimed to be byte-identical across different hardware/quantization environments; governance is achieved through the pinned model and quantization, per-vector validation, artifact pinning with checksums, and full-version regeneration only.
- The approved embedding artifact follows the same pinning discipline as `artifacts/baseline.json`, `app/ai/optimized_program.json`, and the feature 009 text artifact.
- The dataset is a local demo dataset with a documented clean reset path; changing the pinned PostgreSQL image to `pgvector/pgvector:pg16` is a build-time change applied through the clean reset path, with no in-place migration of production data.
- The exact fusion result limit, the lexical/semantic ranking parameters within RRF, and the precise concatenation format of the text fields are plan-phase details within the approved decisions; the spec fixes only the deterministic RRF k=60 constant and the field scope.
- Reranking with the main LLM, multi-vector or per-field retrieval, UI changes, and any document corpus are explicitly out of scope for this feature.
