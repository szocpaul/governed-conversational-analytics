# Feature Sketch: Hybrid Search over Ticket Texts (010)

**Status**: Sketch — NOT yet a spec. Human review requested before any
`/speckit-specify`. Created 2026-10-13 from the earlier RAG discussion
(quoted below) now that feature 009 (synthetic ticket texts) is COMPLETE
and the text foundation exists.
**Depends on**: specs 001-006, 008, 009 complete.

## Origin (from the earlier RAG discussion, human-approved direction)

```text
Natural-language question
    -> typed DSPy planning          (EXISTING)
    -> deterministic validation     (EXISTING)
    -> GraphJin governed query      (EXISTING — structured)
    -> [NEW] governed retrieval     (hybrid search, read-only)
    -> grounded DSPy answer         (EXISTING, extended)
```

The "governed retrieval" gives the same guarantees as the GraphJin
boundary: explicit allowlist (which tables/fields are searchable), result
limit, read-only role, sanitized retrieval trace (which records entered the
context).

Technical approach agreed in that discussion:

- **Lexical side — PostgreSQL full-text search (zero new infra)**:
  `tsvector`/`ts_rank` over the tickets text columns (GIN index).
- **Semantic side — pgvector**: pgvector extension in the existing
  PostgreSQL 16 (no new service); a pinned embedding model (e.g.
  nomic-embed-text via llama.cpp — same "pinned local model, no fallback"
  discipline as the main LLM); embeddings generated in the import pipeline,
  hashed, with provenance.
- **Fusion — deterministic**: RRF (Reciprocal Rank Fusion) or weighted
  score, deterministically, in the app layer — same "deterministic
  validator" pattern as feature 003.

New question types it opens (from the discussion):

| Question | Today | With hybrid search |
|---|---|---|
| "How many P1 tickets are there?" | works | unchanged |
| "Which category has the most tickets?" | works | unchanged |
| "Show me tickets about login problems" | no text search | semantic match: "login" ~ "authentication", "SSO", "password" |
| "What kinds of issues are in Payments & Checkout?" | only count/sub_category list | relevance-ranked text hits |
| "Find tickets similar to ticket 847203" | no | vector similarity |

## Hard constraints from AGENTS.md

- "DO NOT bypass GraphJin with direct arbitrary SQL" — retrieval must be a
  governed, allowlisted, read-only path (either through GraphJin or a
  separately governed read-only channel with the same guarantees; DECIDE).
- "DO NOT give the model unrestricted database credentials" — the retrieval
  path uses the read-only role only.
- "DO NOT switch to another model, hosted provider, or cloud fallback" —
  the embedding model must be local, pinned, verified (same preflight
  discipline as the main LLM); no hosted embedding API.
- "DO NOT simulate model, database, security, baseline, or evaluation
  results" — retrieval quality must be measured with real runs.
- "DO NOT optimize on held-out evaluation cases" — if retrieval ranking is
  tuned, dev/held-out isolation per feature 004 discipline.
- The private LLM/embedding endpoint must never be exposed in the UI,
  errors, or traces.

## Proposed pipeline

```text
data/raw/tickets_texts.jsonl   (pinned, from feature 009)
    |
    v
scripts/generate_embeddings.py  (NEW, offline, pinned embedding model,
    |                            seeded, checkpointed, provenance manifest)
    v
data/raw/tickets_embeddings.jsonl (+ embeddings-manifest.json)  (NEW,
    |                            pinned, versioned, SHA-256)
    v
database/schema.sql             (MODIFIED: tsvector generated column +
                                 GIN index; embedding vector column)
scripts/import_dataset.py       (MODIFIED: atomic import of embeddings)
    |
    v
app/ai/retrieval.py             (NEW: governed retrieval — lexical ts_rank,
                                 semantic pgvector, deterministic RRF
                                 fusion, allowlist + limit + read-only)
app/api/routes.py               (MODIFIED: retrieval integrated into the
                                 query path with sanitized retrieval trace)
```

## Open decisions (need human input before spec)

1. **Retrieval channel**: (a) retrieval through GraphJin (if it can express
   ts_rank / vector ops — GraphJin 3.21.6 capability check needed), or
   (b) a separate governed read-only channel in the app layer with the
   same guarantees (allowlist, limit, read-only role, sanitized trace).
   Recommendation: (b) — GraphJin v3 is a structured-query boundary;
   ranked retrieval is a different shape, and duplicating the guarantees
   in the app layer is explicit and testable. Confirm.
   **Evaluated and rejected (2026-10-13)**: GraphJin's built-in
   "discovery semantic search"
   (https://graphjin.com/configure/discovery-semantic-search/) is
   **catalog-level** search — it embeds schema metadata (table identity
   documents, column facets, relationship neighborhoods) so GraphJin's
   own internal agent can find *which tables/columns* to use. It does not
   index or retrieve row-level content ("caller-owned artifacts, evidence
   payloads, examples containing values remain lexical-only"), so it
   cannot answer "tickets about login problems" over the ticket texts.
   Our feature is row-level content retrieval — the GraphJin feature does
   not cover it. (Noted for completeness: its fusion design — RRF k=60
   with lexical/semantic/relationship weights — matches the approach
   proposed here.)
2. **Embedding model**: which pinned local model? (nomic-embed-text via
   llama.cpp is the discussion's example; needs a `/v1/embeddings`
   capability check on the current endpoint, or a second pinned llama.cpp
   instance). Confirm model choice + endpoint strategy.
3. **Embedding scope**: embed `description` only, or
   short_description + description + resolution_notes (concatenated or
   separate vectors)? Recommendation: one vector per ticket over
   short_description + description (resolution_notes is NULL for 250 open
   tickets; concatenation keeps it simple). Confirm.
4. **Fusion**: RRF (rank-based, robust to scale differences) vs weighted
   score (needs score normalization). Recommendation: RRF, deterministic,
   k=60 standard constant. Confirm.
5. **Retrieval in the answer path**: (a) retrieval as a separate governed
   tool the planner can call (new capability alongside the structured
   query), or (b) retrieval always runs and its hits augment grounding.
   Recommendation: (a) — keeps the structured path untouched and makes
   retrieval opt-in per question type ("tickets about X", "similar to").
   Confirm.
6. **Evaluation**: new dev/held-out cases for retrieval questions per
   feature 004 discipline (physically separate files, no held-out leakage
   into any tuning). Confirm the case counts (e.g. +5 dev, +8 held-out
   incl. security cases like "retrieve tickets containing passwords").
7. **UI**: add a text-search example category to the 008 gallery in THIS
   feature or defer? Recommendation: defer to keep 010 backend-only; the
   gallery can pick it up in a small follow-up. Confirm.

## Testing & quality gates (proposed)

- Unit: RRF determinism (same inputs -> identical ranking), allowlist
  enforcement, result-limit enforcement, read-only role verification,
  embedding-dimension validation, tsvector query construction (no
  arbitrary SQL).
- Integration: end-to-end "tickets about login problems" returns relevant
  Account Access tickets; "similar to ticket 847203" returns same-category
  tickets; retrieval trace lists exactly the records that entered the
  context; write attempts through the retrieval path rejected.
- Security: retrieval allowlist blocks non-allowlisted fields; security
  held-out cases (e.g. "retrieve tickets containing passwords/secrets")
  return nothing prohibited; retrieval trace contains no credentials,
  endpoint details, or prompts.
- Provenance: embeddings-manifest (model ID, dimension, seed, hashes,
  row count) committed; import-manifest extended (additive key).
- Regression: full pytest suite green (currently 500 + new tests).

## Out of scope (this feature)

- Reranking with the main LLM (a later candidate; needs its own
  determinism/latency analysis).
- Multi-vector / per-field retrieval.
- UI changes (see open decision 7).
- Any document corpus / parsing (former "option C").

## Rough size estimate

Embedding generator (~120 lines, mirrors the 009 generator discipline),
schema + import changes, retrieval module (~150 lines), planner/answer
integration, ~20-25 tests. Comparable to feature 009 in size.

## Resolved decisions (pending human review)

*(To be filled after human review of this sketch.)*
