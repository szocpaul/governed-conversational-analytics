# Tasks: Analytics Surface v2

**Spec**: `specs/005-analytics-surface-v2/spec.md`
**Plan**: `specs/005-analytics-surface-v2/plan.md`
**Research**: `specs/005-analytics-surface-v2/research.md` (GraphJin v3 mappings verified live)
**Contract**: `specs/005-analytics-surface-v2/contracts/structured-query-request-v2.md`

**Tests**: REQUIRED per AGENTS.md implementation workflow — write failing
tests first, observe the failure, then implement.

## Phase 1: Foundational (Schema, Validator, GraphQL Builder)

**Purpose**: the typed request v2 surface that all three user stories build
on. No user story work can begin until the schema, validator allowlists, and
GraphQL builder support the new shapes.

- [X] **T001 [P]** Write failing schema tests in `tests/test_schemas_v2.py` for the extended `StructuredQueryRequest`: `group_by` (1-3 allowlisted fields, aggregate-only), `having` (requires non-empty `group_by`; `function` in {count, sum, avg, min, max}; `op` in {eq, ne, gt, gte, lt, lte}; numeric `value`; non-count functions require an allowlisted numeric `field`), `is_null`/`is_not_null` filter ops (value MUST be null), and `ratio` aggregate (`field` REQUIRED, allowlisted boolean column only). Then extend `app/api/schemas.py` (FilterOp, AggregateFunction, `HavingFilter` model, `group_by`/`having` fields, model validators) until the tests pass.
- [X] **T002 [P]** Write failing validator tests in `tests/test_validator.py` covering every new allowlist rule and rejection from the contract's rejection section (group_by on non-allowlisted field, having without group_by, having with string threshold, ratio on non-boolean field, is_null with non-null value, group_by on list operation). Then extend `app/security/validator.py` (`_VALID_OPS`, `_VALID_AGG`, group_by/having/ratio checks) until the tests pass.
- [X] **T003** Write failing GraphQL builder tests in `tests/test_graphql_builder.py` for the verified GraphJin v3 renderings: grouped summary via `distinct: [...]` + aggregate columns with `order_by` on the aggregate column; `is_null`/`is_not_null` filters; ratio via `avg(expr: {case: {arms: [{when: {<field>: {eq: true}}, then: 1.0}], else: 0.0}})`; ratio per group. Then extend `build_graphql` in `app/data/graphjin_client.py` until the tests pass. Verify each rendering once against the live GraphJin instance before writing the unit expectation.
- [X] **T004** Write failing planner-normalization tests in `tests/test_query_program.py`: `group_by` and `having` keys are accepted and normalized; truly unsupported keys (joins, subqueries, union, distinct-as-key) still raise `UnsupportedShapeError`. Then update `_UNSUPPORTED_KEYS`/`_ALLOWED_KEYS`/`_normalize_shape` in `app/ai/query_program.py` until the tests pass.

## Phase 2: User Story 1 — Grouped Aggregations (P1)

**Goal**: grouped breakdown questions ("Which category has the most
tickets?") are answered from executed grouped results.

**Independent test**: ask "Which category has the most tickets?" via
`POST /query`; answer states Payments & Checkout with 483, grounded in
executed groups.

- [X] **T005 [US1]** Write failing pipeline tests in `tests/test_pipeline_groupby.py` for grouped aggregation end-to-end (mocked GraphJin): request with `group_by` → validated → grouped GraphQL → per-group evidence rows → grounded answer; `order_by: "count"` maps to the aggregate column; grouped queries hitting the result limit set `groups_truncated` in evidence. Then implement the grouped-evidence normalization in the pipeline (`app/main.py` / `app/data/graphjin_client.py` response handling) until the tests pass.
- [X] **T006 [US1]** Implement the deterministic application-layer having post-filter (research.md Decision 4): pure function over executed group rows applying the allowlisted `having` comparison, recording `having_applied` (function, op, value, groups_dropped) in evidence. Tests first in `tests/test_pipeline_groupby.py` (groups dropped correctly, zero-group result → stable clarification, no database access from the filter).
- [X] **T007 [US1]** Update `ClassifyQuestion` and `PlanQuery` docstrings in `app/ai/signatures.py` for grouped shapes: grouped breakdowns are now SUPPORTED; document `group_by`, `having`, aggregate ordering, and the 1-3 grouping-field limit. Remove the "NEVER emit group_by" rule. Keep "NEVER output SQL".
- [X] **T008 [US1]** Live end-to-end verification against the running stack: "Which category has the most tickets?" → Payments & Checkout 483; "How many P1 and P2 tickets were created after 2026-01-01, grouped by category?" → per-group counts consistent with P1 = 49, P2 = 163; "Which merchants have more than 50 tickets?" → only groups above 50. Record observed results in `specs/005-analytics-surface-v2/verification-notes.md`.

## Phase 3: User Story 2 — Missing-Value Filtering (P1)

**Goal**: missing-value questions ("tickets with no assigned agent", "open
tickets") are answered from executed is-null filtered results.

**Independent test**: ask "How many tickets have no assigned agent?" via
`POST /query`; answer states 250.

- [X] **T009 [P] [US2]** Write failing pipeline tests in `tests/test_pipeline_null.py` for `is_null`/`is_not_null` end-to-end (mocked GraphJin): filtered count and list requests, "open tickets" = `closed_at is_null` mapping, presence filtering via `is_not_null`. Then implement any missing pipeline handling until the tests pass.
- [X] **T010 [US2]** Update `PlanQuery` docstring in `app/ai/signatures.py`: document `is_null`/`is_not_null` ops and the rule "open = closed_at is_null; closed = closed_at is_not_null". Remove the "never use null as a filter value" rule for these ops.
- [X] **T011 [US2]** Live end-to-end verification: "How many tickets have no assigned agent?" → 250; "List the 5 oldest open tickets" → 5 rows, all `closed_at` null, ordered by `created_at` asc. Record observed results in `specs/005-analytics-surface-v2/verification-notes.md`.

## Phase 4: User Story 3 — Ratio and Percentage Metrics (P2)

**Goal**: ratio questions ("What percentage of tickets breached their
resolution SLA?") are answered from one executed ratio aggregate.

**Independent test**: ask the SLA-breach question via `POST /query`; answer
states 50.4% (1037 of 2057) with the ratio in evidence.

- [X] **T012 [P] [US3]** Write failing pipeline tests in `tests/test_pipeline_ratio.py`: global ratio request → expr-aggregate GraphQL → ratio value in [0, 1] in evidence; empty base set → null ratio → stable clarification (no fabricated number); ratio per group → per-group ratio values. Then implement ratio-evidence normalization until the tests pass.
- [X] **T013 [US3]** Update `PlanQuery` and `GroundAnswer` docstrings in `app/ai/signatures.py`: planner emits `ratio` for percentage questions over boolean flags (replacing the current "use count with a filter instead" rule); the answer program formats ratios as percentages (e.g. 50.4%) and never invents numerator/denominator values.
- [X] **T014 [US3]** Live end-to-end verification: "What percentage of tickets breached their resolution SLA?" → 50.4%; verify the executed evidence contains the ratio 0.5041... Record observed results in `specs/005-analytics-surface-v2/verification-notes.md`.

## Phase 5: Security, Evaluation, and Baseline

- [X] **T015 [P]** Write failing security tests in `tests/test_security_v2.py`: abuse of the new operators to reach non-allowlisted fields (group_by on a blocked field name, ratio on a text field, having with injection-shaped values, is_null on relationship traversal attempts) — all rejected deterministically with zero GraphJin calls; write-shaped requests remain impossible. Then fix any gap found until the tests pass.
- [X] **T016** Extend `evaluation/dev_cases.json` and `evaluation/cases.json` with versioned bumps: new dev cases for each capability (grouped, having, is_null, ratio — keeping the dev set within 12-20 total), new held-out cases including security/unauthorized-access cases abusing the new operators (held-out total >= 20, security cases >= 5, stable unique IDs, zero held-out IDs consumed by optimization). Extend `evaluation/metrics.py` normalization for grouped results and ratio comparison (tolerance 0.001 absolute) with failing tests first in `tests/evaluation/test_metrics.py`.
- [X] **T017** Record a new pre-optimization baseline under feature 004 discipline: pinned versions, temperature zero, cache disabled, representative sample repeated 2-3 times for per-metric noise, then the complete held-out run written to `artifacts/baseline.json` (replacing the pre-extension baseline; keep the old file under a dated name for audit).
- [X] **T018** Optionally run the approved BootstrapFewShot optimization (`metric_threshold=1.0`, `max_bootstrapped_demos=4`, `max_labeled_demos=4`, `max_rounds=1`, `max_errors=3`) ONLY if at least 12 valid labeled dev examples exist after the extension; save `artifacts/optimization-run.json`. Skip with a recorded reason if the dev set is insufficient. Do not run GEPA, MIPROv2, or SIMBA.
- [X] **T019** Run the unchanged held-out set with temperature zero and cache disabled; save `artifacts/current.json`; run `python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json` and verify exit 0 (no prohibited effect, no unauthorized disclosure, no execution-accuracy degradation > 5pp; latency observational only).

## Phase 6: Polish and Closure

- [X] **T020** Run the complete gate set: `pytest -q`, the evaluation run, and the comparison gate; update `README.md` and `quickstart.md` supported-patterns documentation with the three new capabilities and the verified ground-truth examples; update `AGENTS.md` project status if required.
- [X] **T021 MANUAL GATE** — Approved by human reviewer 2026-10-10. Human reviewer runs the quickstart scenarios (grouped, having, is-null, ratio, abuse rejection), reviews the new baseline/current artifacts, security results, and eval-set isolation, and approves or rejects the release. The implementation agent MUST NOT tick this task.

## Dependencies

1. T001-T002 may run in parallel (different files); T003 depends on T001 (schema types); T004 depends on T001.
2. Phase 2 (US1) depends on T001-T004; T005 → T006 → T007 → T008 within the phase.
3. Phase 3 (US2) depends on T001-T004; T009 and T010 may run in parallel; T011 after both.
4. Phase 4 (US3) depends on T001-T004; T012 → T013 → T014.
5. T015 may run in parallel with Phases 2-4 after T001-T004.
6. T016 depends on Phases 2-4 (cases must match implemented behavior).
7. T017 depends on T015-T016; T018 depends on T017; T019 depends on T018 (or directly on T017 when optimization is skipped).
8. T020 depends on T019; T021 depends on T020.

## Parallel Execution Examples

- After T001: `T002` (validator) and `T003` (builder) in parallel.
- After T001-T004: `T005` (US1), `T009` (US2), `T012` (US3), `T015` (security) in parallel.

## Validation Gates

```bash
pytest -q
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

## MANUAL GATE 2: Task Review

- **Approved**
