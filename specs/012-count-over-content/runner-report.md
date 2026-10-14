# Runner Report: Feature 012 — Count over Content

**Feature**: 012-count-over-content | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Status**: IN PROGRESS (skeleton — T001 baseline recorded)

## T001 — Pre-implementation baseline

- **Git commit (HEAD)**: `805ad9a69d343cf6504a26872167178773f629e7` (`805ad9a`)
- **Working-tree state at baseline**: clean except the untracked feature 012
  artifacts (`specs/012-count-over-content/`, `specs/012-count-over-content-sketch.md`).
  No unrelated user changes were overwritten.
- **Baseline test run**: `/usr/bin/python3 -m pytest -q` → **622 passed, 0 failed**
  (1 StarletteDeprecationWarning; duration ~250s). Recorded 2026-10-14T18:40:21.959819+00:00.

## T002 — Endpoint preflight

- **Chat model**: `models\Qwen3.8-27B-UD-Q4_K_M.gguf` present on the pinned
  endpoint; deterministic temp-0 smoke returned `OK`. (Artifact:
  `artifacts/llm-preflight-012.json`.)
- **Embedding model**: `models\embeddinggemma-2-Q8_0.gguf` present on the
  pinned embeddings route; smoke embed returned a 768-dimensional vector.
- No fallback model used; both exact pinned IDs verified via `/v1/models`.
- Private endpoint URLs are NOT recorded (governance).

## Environment (pinned)

- Interpreter: `/usr/bin/python3` (Python 3.14.4)
- dspy 3.4.0, pydantic 2.12.5, httpx 0.28.1, psycopg 3.3.6, pytest 9.0.3
- Stack: docker compose — PostgreSQL `pgvector/pgvector:pg16`, GraphJin 3.21.6

## Live ground-truth verification (2026-10-14)

Verified directly against the real database (read-only):

- total tickets: 2057 (all have `embedding` and `fts`)
- lexical `fts @@ plainto_tsquery('english','login')`: **121** tickets
- structured `priority='P1'`: **112** tickets
- `category='Account Access'`: 360; `sub_category='SSO Failure'`: 90
- hybrid count SQL shape (lexical OR semantic-within-threshold) verified live.

> **Note (assumption recorded)**: the spec Background narrative quoted "login
> appears in the text of 88 tickets". The authoritative ground truth computed
> against the real database with the governed hybrid match condition is **121**
> lexical matches. Per SC-001 the count is "verified against the real database",
> so all labeled `expected.count` values in the evaluation cases are computed
> from the REAL hybrid count query (not the narrative number). The tasks and
> contracts correctly fix only "NOT 0, NOT 25" and leave the exact value to the
> measured run.

---

*(Further sections completed as tasks finish — see task checkboxes in tasks.md.)*
