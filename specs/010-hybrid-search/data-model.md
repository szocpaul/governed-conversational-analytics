# Phase 1 Data Model: Hybrid Search over Ticket Texts

**Feature**: 010-hybrid-search | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## 1. Ticket Embedding (domain entity)

One 768-dimensional vector per ticket, produced by the pinned
EmbeddingGemma-2 model from the ticket's text fields.

| Field | Type (artifact) | Type (DB) | Rules |
|---|---|---|---|
| ticket_id | int (required) | — (join key) | Must exist in pinned tickets.csv; exactly once per artifact |
| embedding | array of 768 floats (required) | `vector(768)` NULL | Dimension exactly 768; all values finite; computed from short_description + description + resolution_notes (available fields only for open tickets) |

**Consistency invariant**: the embedding is derived only from the pinned
feature 009 text fields for the same ticket_id; the NULL rule for
resolution_notes (open tickets) is inherited from the text artifact.

## 2. Embedding Artifact (file entity)

`data/raw/tickets_embeddings.jsonl` — pinned, versioned, committed after
approval.

- One JSON object per line: `{"ticket_id": int, "embedding": [768 floats]}`.
- Line order = pinned `data/raw/tickets.csv` row order (2057 lines).
- SHA-256 recorded in `embeddings-manifest.json`; treated as immutable once
  approved. Any change = new `artifact_version` + full regeneration (never
  partial).

**State transitions**: `(absent)` -> `generating` (checkpoint exists) ->
`generated` (artifact written, checkpoint deleted) -> `validated`
(dimension/coverage checks pass) -> `approved` (artifact frozen) ->
`imported` (present in DB, import manifest extended). A `superseded` state
applies to older versions after regeneration.

## 3. Embedding Provenance Manifest (file entity)

`data/raw/embeddings-manifest.json` — committed alongside the artifact.

| Field | Content |
|---|---|
| artifact_version | e.g. `"1"` (bumped on regeneration) |
| artifact_path / artifact_sha256 / row_count | artifact identity (2057) |
| model_id | exact pinned API model ID (`models\embeddinggemma-2-Q8_0.gguf`) |
| quantization | `"Q8_0"` |
| embedding_dimension | `768` |
| source_gguf / source_gguf_sha256 | `ggml-org/embeddinggemma-2-GGUF` file + its SHA-256 |
| license | `"Apache-2.0"` |
| generator_script_sha256 | SHA-256 of `scripts/generate_embeddings.py` (plus `app/ai/embeddings.py` hash) |
| run_config | `{retries, batching constant, checkpoint path}` actually used |
| created_at | ISO-8601 UTC of run completion |
| validation | `{"suite_passed": true, "checks": [...], "validated_at": <iso>}` |

## 4. Database changes (itsm.tickets)

Additive, marked generated (schema comment
`-- GENERATED (feature 010, embedding + fts from pinned artifact)`):

```sql
-- requires: CREATE EXTENSION IF NOT EXISTS vector;  (pgvector/pgvector:pg16)
embedding  vector(768) NULL,
fts        tsvector GENERATED ALWAYS AS (
             to_tsvector('english',
               coalesce(short_description,'') || ' ' ||
               coalesce(description,'')       || ' ' ||
               coalesce(resolution_notes,''))
           ) STORED
```

Indexes:

```sql
CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw
  ON itsm.tickets USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS tickets_fts_gin
  ON itsm.tickets USING gin (fts);
```

- `embedding` nullable because pre-import databases legitimately lack
  embeddings; populated for all 2057 rows by the import.
- `fts` is a generated STORED column (never written directly); it indexes
  the three generated text fields only.
- Added to the CREATE TABLE definition AND via idempotent
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`
  (same discipline as feature 009, research R6/R11).
- All 19 pinned columns and the 3 feature 009 text columns keep their pinned
  values; import still verifies the pinned checksums first.

## 5. Retrieval Result (runtime entity, not persisted)

The output of one governed retrieval call.

| Field | Type | Rules |
|---|---|---|
| ticket_ids | list[int] | Ranked by fused RRF score; length <= result limit; references only allowlisted tickets |
| scores | list[float] | Fused RRF score per ticket_id, same order; deterministic |
| trace | list[object] | Sanitized retrieval trace: exactly the ticket_ids that entered the model's context; no credentials, endpoint details, or prompts |

## 6. Import-manifest extension (artifacts/import-manifest.json)

One new top-level key `ticket_embeddings` (schema in
contracts/artifact-schemas.md). Existing `dataset` / `import` / `notes` /
`generated_texts` keys are structurally unchanged; feature 001/009 tests
keep passing (research R8 pattern).

## 7. Checkpoint (transient file entity)

`artifacts/tickets_embeddings.checkpoint.jsonl` — append-only, same line
schema as the artifact; deleted on successful completion; never committed;
loaded on startup for resume (research R4).

## Relationships

- `tickets_embeddings.jsonl`.ticket_id -> `tickets.csv`.ticket_id (1:1,
  total both ways — enforced by validation and the import).
- `itsm.tickets`.embedding <- artifact (upsert on ticket_id).
- `itsm.tickets`.fts <- derived (generated column) from the feature 009 text
  columns.
- `embeddings-manifest.json` 1:1 artifact version; referenced by
  `artifacts/import-manifest.json.ticket_embeddings` (path + hashes).
