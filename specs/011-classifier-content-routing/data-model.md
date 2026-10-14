# Phase 1 Data Model: Classifier-Based Content Routing

**Feature**: 011-classifier-content-routing | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

## 1. Routing Decision (runtime entity, not persisted)

The output of the tuned classifier for one question, determining which
governed path handles it.

| Field | Type | Rules |
|---|---|---|
| category | enum string | One of: `content_about`, `content_similar`, `supported`, `ambiguous`, `unsupported`. Unparseable/unknown -> conservative fallback to `supported` (structured path). |
| rationale | string | One short sentence (existing ClassifyQuestion field; observability only). |
| ticket_id | int or null | Present only for `content_similar`; extracted DETERMINISTICALLY (not by the classifier); null otherwise. |

**Consistency invariant**: `content_about`/`content_similar` route to
governed retrieval; `supported` routes to the structured planner;
`ambiguous`/`unsupported` yield a stable clarification/refusal. The routing
decision never changes the downstream governed paths.

## 2. Routing Case (evaluation entity)

A labeled example for tuning (dev) or evaluation (held-out), reusing the
existing `EvalCase` schema (`id`, `category`, `question`, `expected`).

| Field | Type | Rules |
|---|---|---|
| id | string (unique, stable) | Dev IDs and held-out IDs are disjoint; never reused across sets. |
| category | string | One of: `route_content_about`, `route_content_similar`, `route_structured`, `route_unsupported`, or a `security_*` content case. |
| question | string | The natural-language question (includes deep paraphrases). |
| expected | object | `{"route": "<expected category>"}` plus, for `route_content_similar`, `"ticket_id": <int>`; for content_about cases optionally `"relevant_categories": [...]` for relevance spot-checks. |

**Isolation invariant**: dev routing cases (in `evaluation/dev_cases.json`)
and held-out routing cases (in `evaluation/cases.json`) are physically
separate; zero held-out IDs are consumed by tuning (guarded by
`assert_no_held_out_leakage`).

## 3. Tuned Classifier Artifact (file entity)

`app/ai/optimized_program.json` — regenerated to include routing demos.

- Extends the existing structure (`classify`, `plan`, `metadata`): the
  `classify` demos now cover the content categories in addition to the
  structured categories.
- Pinned, versioned, SHA-256-checksummed; immutable once approved.
- Provenance recorded in `artifacts/optimization-run.json` (optimizer
  config, accepted demo IDs, artifact hash, versions, timestamp).

**State transitions**: `(base)` -> `tuning` (BootstrapFewShot running on dev
routing cases) -> `tuned` (artifact written) -> `evaluated` (held-out
routing accuracy + false-routing measured) -> `approved` (threshold met,
artifact frozen) OR `rejected` (threshold not met -> STOP AND REPORT, base
program retained).

## 4. Optimization-Run Record (file entity)

`artifacts/optimization-run.json` — regenerated for the routing tuning run.

| Field | Content |
|---|---|
| optimizer | `"dspy.BootstrapFewShot"` + bounded config (metric_threshold 1.0, max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors 3) |
| metric | routing metric (correct category = 1.0 else 0.0) |
| trainset_ids | development routing case IDs only (leakage-guarded) |
| accepted_demo_ids | the demo IDs BootstrapFewShot accepted into the program |
| output_artifact_sha256 | SHA-256 of the tuned `optimized_program.json` |
| versions | dspy version, exact pinned model ID, timestamp |

## 5. Evaluation Artifacts (file entities)

- `artifacts/baseline.json` — regenerated to include routing metrics
  (routing accuracy, false-routing rate) alongside the existing structured
  metrics; the pre-011 baseline is preserved under a versioned name.
- `artifacts/current.json` — the held-out evaluation including routing
  metrics, compared against the baseline per feature 004 discipline.

## Relationships

- `RoutingCase`.id -> dev/held-out isolation (guarded).
- `Tuned Classifier Artifact` <- produced by `Optimization-Run Record` (1:1).
- `Routing Decision`.category -> dispatch to governed retrieval (feature 010)
  or the structured planner (features 002-005), both unchanged.
