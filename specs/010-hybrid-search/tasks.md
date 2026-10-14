# Tasks: Hybrid Search over Ticket Texts

**Input**: Design documents from `/specs/010-hybrid-search/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — AGENTS.md requires tests before implementation, with the
expected failure observed first. Unit tests stub the embedding endpoint
(scripted HTTP responses); the shipped artifact and all retrieval metrics only
ever come from real recorded runs (research R12).

**Organization**: Tasks are grouped by user story (US1 embedding pipeline = P1,
US2 database storage = P2, US3 governed retrieval = P3, US4 evaluation = P4).
US2 hard-depends on the US1 artifact; US3 hard-depends on US2 (embeddings +
index must exist); US4 hard-depends on US3 (the retrieval path must exist).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3, US4 — maps to spec.md user stories
- All file paths are repository-relative

## Phase 1: Setup

- [x] T001 Record the pre-implementation baseline in `specs/010-hybrid-search/runner-report.md` (skeleton): current git commit + working-tree state, and `pytest -q` result (expect 500 passed, 0 failed). Do not overwrite unrelated user changes.
- [x] T002 [P] Embedding-endpoint preflight per the `app/ai/llm.py` discipline: call `GET /v1/models` on the configured embedding endpoint, verify the exact pinned embedding model ID (`models\embeddinggemma-2-Q8_0.gguf`) is loaded and the `/v1/embeddings` route is supported, run one deterministic embedding smoke request (dimension 768), and confirm `artifacts/embedding-preflight.json` (already recorded 2026-10-13) matches. STOP AND REPORT on any mismatch — no fallback model, no hosted API.
- [x] T003 [P] Add the transient embedding state to `.gitignore`: `artifacts/tickets_embeddings.checkpoint.jsonl` (document the rule in a file comment), mirroring the feature 009 checkpoint rule.

## Phase 2: Foundational (tests first — BLOCKS all user stories)

- [x] T004 [P] Write `tests/unit/test_embeddings_program.py` with a stubbed embedding endpoint (scripted HTTP responses): a valid per-ticket embedding is accepted (dimension exactly 768, all values finite); a wrong-dimension vector rejected; a non-finite (NaN/inf) vector rejected; a malformed HTTP response rejected; the input text is the concatenation of `short_description` + `description` + `resolution_notes` with the recorded separator, and for an open ticket (resolution_notes None) only the available fields are concatenated (never a placeholder); a ticket is retried on failure up to `--max-retries` (default 2) then raises. Run `pytest tests/unit/test_embeddings_program.py -q` and observe FAIL (`app/ai/embeddings.py` missing).
- [x] T005 [P] Write `tests/unit/test_embeddings_checkpoint.py`: checkpoint append after each accepted ticket; load + resume continues with remaining tickets in pinned `tickets.csv` order and never re-accepts or skips a ticket (simulated interruption: partial checkpoint -> resume -> exactly-once coverage of all 2057); torn final line / corrupt JSON fails loudly; checkpoint containing an unknown ticket_id fails loudly; successful completion deletes the checkpoint; `--fresh` discards it explicitly. Run and observe FAIL (`scripts/generate_embeddings.py` missing).
- [x] T006 [P] Write `tests/unit/test_rrf_fusion.py`: deterministic Reciprocal Rank Fusion with k=60 — fused score = sum over sides of 1/(60+rank) with a missing side contributing 0; identical lexical+semantic inputs produce an identical fused ranking; ties break on ticket_id ASC; a ticket present on only one side still ranks; empty inputs produce an empty result. Run and observe FAIL (fusion not implemented).
- [x] T007 [P] Write `tests/unit/test_retrieval_allowlist.py`: the retrieval request validator accepts only the fixed allowlist of searchable fields (the three generated text fields) and rejects any non-allowlisted field; the result limit is clamped to the governed maximum; the tsvector query is built with `plainto_tsquery` and the query text is a bound parameter (assert no arbitrary SQL string interpolation of the query text is possible). Run and observe FAIL (`app/ai/retrieval.py` missing).

## Phase 3: User Story 1 — Governed offline embedding generation with provenance (P1) 🎯 MVP

**Goal**: A maintainer runs one explicit offline command that produces a
strictly validated, provenance-recorded 768-dim embedding artifact for all
2057 tickets via the pinned local EmbeddingGemma-2 model, with
checkpoint/resume and fail-loud behavior.

**Independent Test**: Run embedding twice-interrupted (resume) on a sample,
then full; every vector has dimension 768, coverage is 2057/2057 exactly once,
the run is deterministic, and the manifest is complete — no database involved.

- [x] T008 [P] [US1] Implement `app/ai/embeddings.py` per research R2/R3/R5: an embedding client (httpx, OpenAI-compatible `/v1/embeddings`, exact pinned model ID, no fallback) and per-ticket vector assembly — input text = concatenation of `short_description` + `description` + `resolution_notes` (available fields only when `resolution_notes` is None for open tickets) joined by a recorded separator constant; per-ticket acceptance requiring dimension exactly 768 and all-finite values; bounded identical-request retries then a loud exception. Offline module only — not imported by the runtime query path hot loop. Iterate until T004 passes.
- [ ] T009 [US1] Implement `scripts/generate_embeddings.py` per contracts/embedder-cli.md (depends on T008): verify pinned `data/raw/tickets_texts.jsonl` SHA-256 against `data/raw/texts-manifest.json` and `data/raw/tickets.csv` SHA-256 against `artifacts/import-manifest.json` before any embedding call; verify endpoint + exact pinned embedding model ID (exit 2 on mismatch/unreachable/unsupported); embed tickets in pinned CSV order with bounded retries (default 2, then exit 1 naming the failing ticket); append-only checkpoint at `artifacts/tickets_embeddings.checkpoint.jsonl` with resume-by-default and `--fresh`; on completion write `data/raw/tickets_embeddings.jsonl` (2057 lines, CSV order, `{"ticket_id", "embedding"}` per line) and `data/raw/embeddings-manifest.json` (schema per contracts/artifact-schemas.md), then delete the checkpoint; never write to the database; never modify pinned raw files. Iterate until T005 passes.
- [x] T010 [US1] Live sample dry-run (quickstart step 1): `python scripts/generate_embeddings.py --sample 10 --output /tmp/tickets_embeddings_sample.jsonl`, and verify each vector has dimension 768 and open tickets in the sample used only the available fields. Record the outcome in the runner notes. Any shape problem is fixed in the module/CLI (T008/T009), never by hand-editing output.
- [x] T011 [US1] Live resume test (quickstart step 2): start `--sample 25`, interrupt after some tickets, confirm `artifacts/tickets_embeddings.checkpoint.jsonl` exists, re-run and confirm resume-from-checkpoint (accepted ids loaded, remaining only) completing with exactly 25 unique vectors. Record the outcome.
- [x] T012 [US1] Full live embedding run (quickstart step 3): `python scripts/generate_embeddings.py` — expect 2057 tickets; verify exit 0, 2057-line artifact, manifest complete (model ID, quantization Q8_0, dimension 768, source GGUF + SHA-256, license Apache-2.0, script + module hashes, run config incl. retries used, created_at), checkpoint deleted. Record runtime (observational only).
- [x] T013 [US1] Validate the full artifact (quickstart step 4): verify coverage 2057/2057 exactly once, every vector dimension 768 and finite, and re-check `artifact_sha256` against the file on disk. On any failure, fix at source (module or CLI) and regenerate per the full-run policy; never patch the artifact by hand. Record the validation result into `data/raw/embeddings-manifest.json` (`validation` block). Artifact approval (human-approved, recorded) is a precondition for US2 import per FR-005.

## Phase 4: User Story 2 — Database storage of embeddings and lexical index with provenance (P2)

**Goal**: The approved pinned embedding artifact lands in `itsm.tickets` as a
vector column, plus a generated full-text-search column with a GIN index, via
the existing atomic, idempotent import, on the pinned `pgvector/pgvector:pg16`
image, with provenance recorded in the import manifest.

**Independent Test**: Reset -> initialize -> import; all 2057 tickets have a
768-dim embedding, the fts column and both indexes exist, pinned columns are
byte-identical to source, re-import is idempotent.

- [x] T014 [US2] Write `tests/integration/test_embeddings_import.py`: after import, all 2057 tickets have a non-null embedding of dimension 768; the `fts` generated column and the `tickets_embedding_hnsw` and `tickets_fts_gin` indexes exist; the `vector` extension is present and its version recorded; spot-check pinned columns against `data/raw/tickets.csv` and the feature 009 text columns against `data/raw/tickets_texts.jsonl` (unchanged); re-import is idempotent; a tampered embedding artifact (checksum mismatch) fails with zero database changes; `artifacts/import-manifest.json` gains the `ticket_embeddings` key per contracts/artifact-schemas.md while `dataset`, `import`, and `generated_texts` keep their shape (feature 001/009 compatibility). Run and observe FAIL (import does not load embeddings yet).
- [x] T015 [US2] Update `compose.yml` to pin `postgres` to `pgvector/pgvector:pg16` (research R6/R11), and update `database/schema.sql` per contracts/database-schema.md: `CREATE EXTENSION IF NOT EXISTS vector`; add `embedding vector(768) NULL` and the generated `fts tsvector ... STORED` column to the `itsm.tickets` CREATE TABLE with `-- GENERATED (feature 010 ...)` comments, plus idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` statements (HNSW on embedding with `vector_cosine_ops`, GIN on fts). Recreate the stack on the new image via the clean reset path and run `python scripts/initialize_database.py`; verify the extension, columns, and indexes exist.
- [x] T016 [US2] Extend `scripts/import_dataset.py` per contracts/database-schema.md (depends on T015): inside the SAME single transaction — verify the embedding artifact SHA-256 against `data/raw/embeddings-manifest.json`, ticket_id coverage == pinned 2057, and every vector dimension == 768 (refuse loudly otherwise); upsert the embedding column per ticket (`ON CONFLICT (ticket_id) DO UPDATE` of the embedding column only); post-import count + dimension checks inside the transaction; on success extend `artifacts/import-manifest.json` with the `ticket_embeddings` key (paths, both SHA-256 hashes, artifact_version, row_count, embedding_dimension, imported_at) without altering existing keys. Iterate until T014 passes.
- [x] T017 [US2] Exercise the clean reset path end-to-end (quickstart step 5): `python scripts/reset_database.py && python scripts/initialize_database.py && python scripts/import_dataset.py` reproduces the full state on the pgvector image (2057 tickets, embeddings + fts populated, indexes present), and `pytest tests/integration/test_database_initialization.py tests/integration/test_database_import.py tests/integration/test_ticket_texts_import.py -q` stays green (feature 001/009 discipline unbroken).

## Phase 5: User Story 3 — Governed hybrid retrieval as a planner tool (P3)

**Goal**: Content questions ("tickets about login problems", "tickets similar
to ticket 847203") return relevance-ranked, grounded results through a
governed, read-only retrieval channel with deterministic RRF fusion and a
sanitized trace; the structured query path is untouched.

**Independent Test**: Through the conversational query path, "tickets about
login problems" returns relevant Account Access tickets with a retrieval
trace; "similar to ticket 847203" returns same-category tickets; structured
questions are unchanged; write attempts through the retrieval path are
rejected with zero database changes.

- [x] T018 [P] [US3] Implement `app/ai/retrieval.py` per contracts/retrieval-api.md and research R1/R7/R8: a governed read-only channel connecting as `itsm_readonly`; typed request (`mode` about/similar, `query_text`/`ticket_id`, `limit` clamped to the governed maximum); fixed parameterized SQL — lexical `ts_rank(fts, plainto_tsquery('english', :q))` with `fts @@ plainto_tsquery(...)`, semantic `embedding <=> :qvec` cosine distance, deterministic RRF k=60 fusion with ticket_id ASC tie-break; fixed field allowlist (the three generated text fields); result limit enforced; sanitized retrieval trace (ticket_ids only). For `mode=similar`, the reference ticket's stored embedding is the semantic query vector and its text is the lexical query. Iterate until T006 and T007 pass.
- [x] T019 [US3] Extend `app/api/schemas.py` and `app/api/routes.py` per research R9 (depends on T018): add the typed retrieval request/response and retrieval-trace event shapes; integrate the retrieval tool into the query path as an opt-in per question type (the planner routes content questions to retrieval; structured analytical questions stay on the GraphJin path unchanged); ground the answer on the retrieval result and return a stable clarification/refusal when retrieval yields no evidence (never fabricate); attach the sanitized retrieval trace; keep the overall request safety timeout and result-size cap independent.
- [ ] T020 [US3] Write `tests/integration/test_retrieval_e2e.py` (depends on T019, live stack): "tickets about login problems" returns relevant Account Access tickets with a retrieval trace listing exactly the ticket_ids that entered the context; "find tickets similar to ticket 847203" returns same-category tickets ranked by similarity; a structured question ("how many P1 tickets") is answered by the structured path exactly as before; a no-match content query returns a stable clarification/refusal; identical retrieval queries produce identical fused rankings (determinism). Run against the live stack and iterate until pass.
- [ ] T021 [US3] Write `tests/integration/test_retrieval_security.py` (depends on T019, live stack): INSERT/UPDATE/DELETE/TRUNCATE/CREATE/ALTER/DROP attempts through the retrieval path are rejected with zero database changes; the retrieval trace contains no credentials, private endpoint details, complete prompts, or SQL text; a security retrieval query (e.g. "retrieve tickets containing passwords/secrets") returns nothing prohibited. Run against the live stack and iterate until pass.

## Phase 6: User Story 4 — Evaluation of retrieval quality under dataset isolation (P4)

**Goal**: Retrieval quality is measured with real runs under feature 004
isolation discipline; security retrieval cases return nothing prohibited; no
held-out leakage into tuning.

**Independent Test**: New dev (+5) and held-out (+8) retrieval cases exist in
physically separate files; the held-out evaluation runs at temperature 0 with
cache disabled; security retrieval cases return nothing prohibited; zero
held-out IDs appear in any tuning input.

- [ ] T022 [P] [US4] Add +5 retrieval development cases to `evaluation/dev_cases.json` (physically separate from held-out; stable unique IDs; content/similarity question types with labeled expected relevant tickets).
- [ ] T023 [P] [US4] Add +8 held-out cases to `evaluation/cases.json` (physically separate from dev; stable unique IDs; including security retrieval cases such as "retrieve tickets containing passwords/secrets" that must return nothing prohibited).
- [ ] T024 [US4] Run the held-out evaluation per feature 004 discipline (depends on T022, T023): `python -m evaluation.run --cache=false --output artifacts/current.json` then `python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json`; verify retrieval quality metrics are reported from real runs, security retrieval cases return nothing prohibited, and zero held-out IDs appear in any tuning input. Record per-request latency, median, p90, max as observational (never a gate).

## Phase 7: Polish & Validation

- [ ] T025 Run the full validation gate set from `specs/010-hybrid-search/quickstart.md` steps 1-9: `pytest -q` green (all 500 pre-existing + new tests, SC-010); full artifact validation passes; retrieval governance/security checks pass. Fix any failure at its source.
- [ ] T026 Verify artifact pinning (SC-001): recompute SHA-256 of `data/raw/tickets_embeddings.jsonl` and confirm it equals `embeddings-manifest.json.artifact_sha256` and the `ticket_embeddings` record in `artifacts/import-manifest.json`; confirm the approved artifact is committed to Git and byte-stable across a fresh checkout/read.
- [ ] T027 Complete `specs/010-hybrid-search/runner-report.md` per the AGENTS.md Required Final Report: completed/blocked task IDs, files changed, commits, exact pinned versions (incl. pgvector image + extension version and the embedding model ID/quantization), validation commands with exact results, live-embedding summary (tickets, retries, runtime as observational), retrieval governance/security-effect and disclosure results, retrieval latency (median, p90, max, observational), known limitations.

## Dependencies

```text
T001 -> T002/T003 (baseline first; preflight + gitignore parallel)
T004/T005/T006/T007 parallel (different test files) — all must FAIL before implementation
T004 -> T008; T005 -> T009; T008 -> T009 (CLI uses the embeddings module)
T009 -> T010 -> T011 -> T012 -> T013 (sample -> resume -> full run -> validation)
T013 -> T014/T015/T016 -> T017 (import only after the approved artifact)
T015 -> T016 (import needs the columns/indexes)
T006/T007 -> T018 (retrieval uses fusion + allowlist); T018 -> T019 -> T020/T021
T019 -> T022/T023 -> T024 (evaluation needs the retrieval path)
T025/T026 depend on all stories; T027 last
```

User stories are NOT parallel here: US2 consumes the US1 artifact; US3
consumes the US2 database state; US4 consumes the US3 retrieval path. Within
phases, the marked [P] tasks are parallel.

## Parallel Execution Examples

- T004, T005, T006, T007 written in parallel (four different test files).
- T002 and T003 in parallel during Setup.
- T008 (`app/ai/embeddings.py`) and the fusion/allowlist implementation prep in
  parallel after their tests exist.
- T022 and T023 in parallel (separate evaluation files).

## Implementation Strategy

1. Setup + Foundational (T001-T007): baseline, preflight, failing tests.
2. MVP = Phase 3 (US1): the validated, provenance-recorded embedding artifact
   alone delivers the foundation value.
3. Increment: US2 (storage/import on the pgvector image), then US3 (governed
   retrieval), then US4 (evaluation under isolation).
4. Polish: gates + pinning verification + runner report.

## Notes

- [P] tasks = different files, no dependencies
- Tests MUST be observed failing before their implementation task starts
- The embedding artifact is NEVER hand-edited; fixes go to the module or CLI,
  followed by regeneration per the full-run policy
- Commit after each task or logical group; keep task IDs in commit messages
- The private chat/embedding endpoints, credentials, and prompts must not
  appear in user-facing output, committed files, or traces
- Retrieval latency is observational only — never a pass/fail gate
- UI changes are out of scope (human decision 7); the 008 gallery picks up
  text-search examples in a follow-up
