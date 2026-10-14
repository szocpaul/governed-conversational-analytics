# Quickstart Validation: Hybrid Search over Ticket Texts

**Feature**: 010-hybrid-search | **Date**: 2026-10-13

Runnable end-to-end validation for the feature. Contracts referenced:
[embedder-cli](contracts/embedder-cli.md),
[retrieval-api](contracts/retrieval-api.md),
[artifact-schemas](contracts/artifact-schemas.md),
[database-schema](contracts/database-schema.md).

## Prerequisites

1. Stack healthy on the pinned `pgvector/pgvector:pg16` image:
   `docker compose up -d` (PostgreSQL with pgvector, GraphJin 3.21.6), `.env`
   configured per `.env.example` with the pinned chat AND embedding endpoint
   values (`LLM_*` and `EMBED_*`).
2. Pinned data verified: `python scripts/import_dataset.py` succeeds on the
   current dataset (checksums match `artifacts/import-manifest.json`), and the
   feature 009 text artifact is present and approved.
3. Embedding endpoint verified: the exact pinned embedding model ID responds
   on the embeddings route (see `artifacts/embedding-preflight.json`; the
   embedder re-verifies itself).
4. Schema updated: `python scripts/initialize_database.py` (idempotent; creates
   the vector extension, the embedding column, the fts column, and the indexes).

## Step 1 — Embedding dry-run on a small sample

```bash
python scripts/generate_embeddings.py --sample 10 --output /tmp/tickets_embeddings_sample.jsonl
```

Expected: exit 0; 10 validated vectors (each dimension 768) in tickets.csv
order; stderr log shows endpoint verification and retries used.

## Step 2 — Resume test (simulated interruption)

```bash
python scripts/generate_embeddings.py --sample 25 --output /tmp/tickets_embeddings_resume.jsonl &
# kill the process after some tickets (Ctrl-C or kill <pid>)
ls artifacts/tickets_embeddings.checkpoint.jsonl   # checkpoint exists
python scripts/generate_embeddings.py --sample 25 --output /tmp/tickets_embeddings_resume.jsonl
```

Expected: the second run RESUMES from the checkpoint (log shows accepted
ticket_ids loaded, remaining only), completes with exactly 25 unique vectors,
never restarting from scratch, never skipping. (Unit tests cover the same
semantics hermetically with a stubbed endpoint.)

## Step 3 — Full embedding run

```bash
python scripts/generate_embeddings.py
```

Expected: exit 0 after 2057 tickets; `data/raw/tickets_embeddings.jsonl`
(2057 lines) + `data/raw/embeddings-manifest.json` written; checkpoint
deleted; manifest records model ID, quantization, dimension 768, source GGUF
SHA-256, hashes, created_at.

## Step 4 — Deterministic validation

The embedder validates inline (dimension 768, finite values, coverage
2057/2057 exactly once). Re-verify by checking the manifest's
`validation.suite_passed == true` and re-checking `artifact_sha256` against
the file on disk.

## Step 5 — Atomic import

```bash
python scripts/import_dataset.py
```

Expected: exit 0; single transaction upserts pinned data + the embedding
column for all 2057 tickets; `artifacts/import-manifest.json` gains the
`ticket_embeddings` key; re-running is idempotent. Reset-path check:
`python scripts/reset_database.py && python scripts/initialize_database.py &&
python scripts/import_dataset.py` reproduces the same state on the pgvector
image.

## Step 6 — Retrieval smoke test

Through the conversational query path (`POST /query`):

- "Show me tickets about login problems" -> relevant Account Access tickets
  returned (semantic match: login ~ authentication/SSO/password), with a
  sanitized retrieval trace listing the ticket_ids that entered the context.
- "Find tickets similar to ticket 847203" -> same-category tickets ranked by
  similarity.
- "How many P1 tickets are there?" -> answered by the structured path exactly
  as before (retrieval is opt-in and does not alter it).

Expected: content questions return ranked, grounded results; the structured
question is unchanged; the trace contains no credentials, endpoints, or
prompts.

## Step 7 — Governance and security checks

- Attempt any write through the retrieval path -> rejected; database
  unchanged (zero changes).
- Ask a security retrieval question (e.g. "retrieve tickets containing
  passwords/secrets") -> returns nothing prohibited; trace hygiene holds.
- Inspect the retrieval configuration -> searchable fields limited to the
  allowlist (the three generated text fields); result limit enforced;
  read-only role used.

## Step 8 — Evaluation under isolation

```bash
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

Expected: the new held-out retrieval cases (+8, incl. security) are evaluated
with real runs; security retrieval cases return nothing prohibited; zero
held-out IDs appear in any tuning input; the comparison gate behaves per
feature 004 discipline.

## Step 9 — Full regression

```bash
pytest -q
```

Expected: all 500 pre-existing tests pass plus the new unit/integration tests
of this feature; no failures introduced.

## Done criteria mapping

Steps 1-4 -> SC-002, SC-003, SC-004; Step 5 -> FR-010 + import manifest
extension; Step 6 -> SC-005, SC-006, SC-007; Step 7 -> SC-007, SC-008;
Step 8 -> SC-008, SC-009; Step 9 -> SC-010. Artifact checksum stability
(SC-001) is verified by re-checking `artifact_sha256` after approval.
