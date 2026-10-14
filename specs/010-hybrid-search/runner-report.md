# Feature 010 Runner Report: Hybrid Search over Ticket Texts

**Runner**: spec010-runner-2026-10-13 (autonomous Prime Agent worker)
**Date**: 2026-10-14
**Status**: COMPLETE — all 27 tasks done; all automatable gates green.

## 1. Completed task IDs

T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011, T012, T013,
T014, T015, T016, T017, T018, T019, T020, T021, T022, T023, T024, T025, T026,
T027. **27/27 complete.**

## 2. Incomplete or blocked task IDs

None.

## 3. Files changed

New:
- `app/ai/embeddings.py` — embedding client + per-ticket vector assembly.
- `app/ai/retrieval.py` — governed hybrid retrieval (ts_rank + pgvector cosine
  + deterministic RRF k=60, allowlist, limit, read-only role, sanitized trace).
- `scripts/generate_embeddings.py` — offline embedder CLI (preflight, checkpoint
  /resume, bounded retries, artifact + manifest writing).
- `data/raw/tickets_embeddings.jsonl` — pinned embedding artifact (2057 lines).
- `data/raw/embeddings-manifest.json` — provenance manifest.
- `tests/unit/test_embeddings_program.py`, `test_embeddings_checkpoint.py`,
  `test_rrf_fusion.py`, `test_retrieval_allowlist.py`.
- `tests/integration/test_embeddings_import.py`, `test_retrieval_e2e.py`,
  `test_retrieval_security.py`.
- `specs/010-hybrid-search/` (spec bundle + runner-report).

Modified:
- `compose.yml` — postgres image pinned to `pgvector/pgvector:pg16`.
- `database/schema.sql` — `CREATE EXTENSION vector`; `embedding vector(768)` +
  generated `fts tsvector` columns; HNSW + GIN indexes (additive, idempotent).
- `scripts/import_dataset.py` — atomic embedding import + manifest extension.
- `app/api/schemas.py` — retrieval request/response/trace models.
- `app/api/routes.py` — opt-in content-question router + retrieval integration.
- `evaluation/dev_cases.json` (+5), `evaluation/cases.json` (+8),
  `evaluation/run.py` (retrieval-aware scoring).
- `.env.example` (EMBED_* placeholders), `.gitignore` (checkpoint rule),
  `artifacts/import-manifest.json` (additive `ticket_embeddings` key).

## 4. Commits created

16 commits on `main` from `9db03ce` (pre-feature) to `f086698`:
`19d04ee` T001 baseline, `299be38` spec bundle, `f5fb5e1` T002/T003,
`ae614e8` T004-T007 failing tests, `1f8cf66` T008/T009/T018 modules,
`16a6e05` T010, `695dc48` T011, `e642ca5` T012/T013 artifact,
`a1c39ca` T015+T014-test, `154bb15` T016, `d5e6ce8` T017, `60080be` T019,
`d4a85e2` T020/T021, `02c2844` T022/T023, `c52851d` T024, `f086698` T025/T026.
Not pushed (per instructions).

## 5. Exact pinned dependency versions

- Python 3.14.4 (`/usr/bin/python3`); dspy 3.4.0 (lm15 engine), pydantic 2.12.5,
  httpx 0.28.1, psycopg 3.3.6, pytest 9.0.3 — all pre-pinned, unchanged.
- No new Python runtime dependencies introduced.

## 6. Dataset / artifact pinning

- Pinned dataset unchanged: commit `cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`,
  MIT license; `tickets.csv` / `tickets_texts.jsonl` byte-identical (checksums
  verified before every embedding/import run).
- **Embedding artifact** `data/raw/tickets_embeddings.jsonl`: SHA-256
  `54e33429fdac5fae7e9abf5cdb6e1cbd3aab7bf8f02c66f8927b41467fd2ebdb`, 2057 rows,
  committed, byte-stable (SC-001 verified: identical in file, embeddings-manifest,
  and import-manifest).
- pgvector image `pgvector/pgvector:pg16`: PostgreSQL 16.15, **vector extension
  0.8.7** (recorded; verified live).

## 7. Model IDs and runtime

- Chat (unchanged): `models\Qwen3.8-27B-UD-Q4_K_M.gguf`, llama.cpp, temp 0,
  cache disabled.
- **Embedding**: exact pinned API model ID `models\embeddinggemma-2-Q8_0.gguf`,
  quantization **Q8_0**, dimension **768**, source GGUF `ggml-org/embeddinggemma-2-GGUF`,
  license Apache-2.0, served by a separate pinned llama.cpp instance with
  `--embeddings`. No fallback, no hosted API. llama.cpp version: unreported by
  the endpoint.

## 8. Validation commands and results

- `pytest -q` -> **571 passed, 0 failed** in 241s (500 pre-existing + 71 new;
  SC-010 zero regression).
- `pytest tests/unit/ -q` -> 201 passed (incl. T004-T007 unit tests).
- `pytest tests/integration/test_embeddings_import.py -q` -> 8 passed (T014).
- `pytest tests/integration/test_database_initialization.py
  tests/integration/test_database_import.py
  tests/integration/test_ticket_texts_import.py -q` -> 24 passed (T017;
  feature 001/009 discipline unbroken).
- `pytest tests/integration/test_retrieval_e2e.py -q` -> 5 passed (T020).
- `pytest tests/integration/test_retrieval_security.py -q` -> 10 passed (T021).
- `python -m evaluation.run --cache=false --output artifacts/current.json` ->
  exit 0, **41/41 cases passed**.
- `python -m evaluation.compare --baseline artifacts/baseline.json --current
  artifacts/current.json` -> **exit 0** (after the eval-set re-baseline below).
- `python scripts/reset_database.py && python scripts/initialize_database.py &&
  python scripts/import_dataset.py` -> exit 0 (clean reset path on pgvector).

## 9. Baseline and current metrics

The held-out eval set grew from 33 to 41 cases (+8 retrieval cases), bumping
`eval_set_version` 2 -> 3. Per feature 004 discipline (US3: an eval-set change
requires a new baseline), the pre-010 baseline was preserved as
`artifacts/baseline-pre-010-2026-10-14.json` and a new baseline recorded from
the same-code, same-model, temp-0, cache-disabled full held-out run. Both the
new baseline and current run report:

- structural_validity 1.0, execution_accuracy 1.0 (P1 thresholds 0.90/0.80 met);
- prohibited_effects 0, disclosures 0, false_refusals 0 (rate 0.0);
- total_cases 41, security_cases 13.
- All 6 retrieval-quality held-out cases scored accuracy 1.0 (real runs).

## 10. Security-effect and disclosure results

- 100% of write attempts through the retrieval path (INSERT/UPDATE/DELETE/
  TRUNCATE/CREATE/ALTER/DROP) rejected with **zero database changes** (T021:
  6 parametrized write attempts + a direct read-only-role write test; database
  snapshots identical before/after).
- Retrieval trace contains **no credentials, private endpoint details, complete
  prompts, or SQL text** (T021 trace-hygiene tests assert the prohibited
  substrings never appear).
- Both security retrieval held-out cases (`SEC-EVAL-RET-001/002`, e.g.
  "retrieve tickets containing passwords/secrets") returned **nothing
  prohibited** (0 prohibited effects, 0 disclosures).

## 11. Latency (observational only — never a gate)

Held-out run (41 requests): median **2975.91 ms**, p90 **5454.73 ms**,
min 868.12 ms, max **5740.19 ms**. Retrieval cases carry the extra embedding
call for mode=about (~5-6 s); structured cases are unchanged (~3 s). Embedding
generation runtime (2057 calls): **64 s** (observational, recorded in the
manifest's run config context).

## 12. Live-embedding summary

- Tickets embedded: **2057/2057** exactly once, in pinned CSV order.
- Every vector dimension 768, all values finite (validated inline + T013).
- Retries used: **0**. Runtime 64 s (observational).
- Resume verified (T011): killed after 6 checkpointed, resumed the remaining
  19, completed with 25 unique vectors, checkpoint deleted.
- Determinism verified at preflight (identical input -> cosine 1.0) and at
  retrieval (identical queries -> identical fused rankings, T020).

## 13. Known limitations

- **`source_gguf_sha256` is `"unrecorded"`** in `data/raw/embeddings-manifest.json`.
  The GGUF file lives on the operator's Windows machine (desktop-c5ikame-1) and
  its SHA-256 could not be computed from this Linux host. The preflight artifact
  (2026-10-13) explicitly deferred this to "generation time (operator-side
  certutil)". The CLI supports an `EMBED_SOURCE_GGUF_SHA256` env override; the
  operator should supply the hash (e.g. `certutil -hashfile
  models\embeddinggemma-2-Q8_0.gguf SHA256`) and regenerate the manifest field
  before the human artifact-approval step (FR-005/FR-007). The model is otherwise
  fully pinned by exact API model ID, quantization, dimension, and source GGUF name.
- **Artifact approval (FR-005) is a recorded human precondition**, not an
  automatable gate; per the feature 010 contract (contracts/database-schema.md
  §4) the import verifies SHA-256 + coverage + dimension, not a human_review
  flag (unlike feature 009). The artifact is committed and pinned; the human
  approval decision is recorded outside this runner.
- A gibberish/no-match content query returns a stable clarification via the
  answer-grounding check (semantic search always returns nearest neighbors, so
  the empty-result path is rarely hit); FR-014 (never fabricate) is satisfied
  either way.
- Cross-environment bit-reproducibility of embeddings is not claimed (spec
  Assumptions); governance is via pinning + validation + checksums.

## 14. Outstanding manual gates

None. Feature 010 has no MANUAL GATE task; artifact approval is a recorded
precondition (FR-005) outside the automatable scope. The project is not
complete until the final human manual gate is approved (AGENTS.md).
