# Phase 1 Data Model: Count over Content

**Feature**: 012-count-over-content | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

## 1. Content Count (runtime entity, not persisted)

The true total of tickets whose text matches a content query (lexical OR
semantic-within-threshold), computed by a governed hybrid count query.

| Field | Type | Rules |
|---|---|---|
| count | int | The true total of matching tickets; NEVER limited by the retrieval result cap; 0 is a valid grounded result (the text was actually searched). |
| example_ticket_ids | list[int] | Up to 5 example matches for transparency; capped, sanitized; same match condition as the count. |
| trace | list[object] | Sanitized: the count + example ids; no credentials, endpoint details, SQL text, or prompts. |

**Consistency invariant**: a ticket is counted once whether it matches
lexically, semantically, or both (OR semantics). The count is grounded; if
the query fails or the threshold is absent, the answer path returns a stable
clarification/dependency error (never a fabricated number).

## 2. Semantic-Match Threshold (file entity)

`count-threshold.json` — the calibrated, versioned, committed parameter.

| Field | Content |
|---|---|
| threshold | float (cosine distance, e.g. 0.35) — a semantic "match" is `embedding <=> qvec <= threshold` |
| version | e.g. `"1"` (bumped on recalibration) |
| calibration_method | `"deterministic distance sweep over dev count cases"` |
| calibration_dev_ids | the development count case IDs used (leakage-guarded) |
| created_at | ISO-8601 UTC |
| artifact_sha256 | SHA-256 of this file's canonical form (recorded in the import/eval manifest) |

**Invariant**: never hardcoded; if absent or uncalibrated, the count path
stops and reports (FR-005).

## 3. Count-over-Content Case (evaluation entity)

A labeled example for calibration (dev) or evaluation (held-out), reusing
the existing `EvalCase` schema (`id`, `category`, `question`, `expected`).

| Field | Type | Rules |
|---|---|---|
| id | string (unique, stable) | Dev IDs and held-out IDs are disjoint. |
| category | string | `count_content` or a `security_*` count case. |
| question | string | The count-over-content question (includes paraphrases). |
| expected | object | `{"count": <int>}` (the labeled true count) plus optionally `"relevant_categories": [...]` for spot-checks. |

**Isolation invariant**: dev and held-out cases are physically separate;
zero held-out IDs are consumed by calibration (guarded by
`assert_no_held_out_leakage`).

## 4. Routing Decision (extended)

The feature 011 Routing Decision gains a `content_count` category.

| Category | Routed to |
|---|---|
| `content_count` | the governed hybrid count path (this feature) |
| `content_about` / `content_similar` | governed retrieval list (feature 010, unchanged) |
| `supported` | structured planner (unchanged) |
| `ambiguous` / `unsupported` | stable clarification/refusal (unchanged) |

## 5. Evaluation Artifacts (file entities)

- `artifacts/baseline.json` — regenerated to include count metrics (count
  accuracy, false-count rate); the pre-012 baseline is preserved.
- `artifacts/current.json` — the held-out evaluation including count
  metrics, compared against the baseline per feature 004 discipline.

## Relationships

- `Count-over-Content Case`.id -> dev/held-out isolation (guarded).
- `Semantic-Match Threshold` <- produced by deterministic calibration over
  dev count cases (1:1 with a calibration run).
- `Content Count` <- computed by the governed hybrid count query using the
  `Semantic-Match Threshold`.
- `Routing Decision`.category == `content_count` -> dispatch to the count
  path.
