# Phase 0 Research: Analytics Surface v2

**Date**: 2026-10-10
**Method**: live probes against the running GraphJin 3.21.6 stack
(`http://127.0.0.1:8081/api/v1/graphql`), GraphJin master-branch
documentation (`website/content/core/aggregations-functions.md`,
`FEATURES.md`), and qcode source inspection. Every capability claim below
was executed and observed.

## Decision 1: GROUP BY via GraphJin `distinct` + aggregate columns

**Decision**: Map `group_by: [field, ...]` to GraphJin's grouped-summary
form: `entity(distinct: [field], order_by: {...}, limit: n) { field
count_<pk> avg_<num> ... }`.

**Evidence** (live):
- `{ tickets(distinct: [category], order_by: {count_ticket_id: desc}, limit: 3) { category count_ticket_id } }`
  returned `Payments & Checkout 483` first — matches the T010 ground truth.
- Multiple grouping fields work (`distinct: [category, priority]`).
- Ordering by the aggregate column (`order_by: {count_ticket_id: desc}`)
  works and is required for "which group has the most" questions.

**Rationale**: native GraphJin capability; stays inside the governed
read-only surface; no SQL construction.

**Alternatives considered**:
- Hasura-style `tickets_aggregate(group_by: ...)` — rejected by GraphJin
  ("only aggregate function fields are supported").
- Client-side grouping over a `list` pull — violates result-limit semantics
  (groups computed over a truncated page would be wrong) and moves
  aggregation out of the governed layer.

## Decision 2: is-null filtering via native `is_null` operator

**Decision**: Add `is_null` and `is_not_null` filter ops to the request
schema; map to GraphJin `where: {field: {is_null: true|false}}`.

**Evidence** (live):
- `{ tickets(where: {assigned_agent_id: {is_null: true}}, limit: 2) { ticket_id } }`
  returned rows; the ground-truth count is 250.
- GraphJin also accepts `eq: null` in v3, but the explicit `is_null` op is
  clearer in the typed schema and validator, so `is_null`/`is_not_null` are
  the only null-related ops added.

**Rationale**: native support; the validator change is a small allowlist
extension (ops set + "value must be null/absent for these ops" rule).

**Alternatives considered**:
- Derived `status: open/closed` column — rejected at spec clarification
  (Q2: A). "Open" maps to `closed_at is_null` in the planner signature.

## Decision 3: Ratio via GraphJin expression aggregate

**Decision**: Add a `ratio` aggregate to the request schema with shape
`{function: "ratio", field: <boolean flag field>}` (v1 supports boolean-flag
ratios only). Map to a single GraphJin expression aggregate:
`avg(expr: {case: {arms: [{when: {<field>: {eq: true}}, then: 1.0}], else: 0.0}})`.

**Evidence** (live):
- `{ tickets { breach_ratio: avg(expr: { case: { arms: [ { when: { resolution_breached: { eq: true } }, then: 1.0 } ], else: 0.0 } }) } } }`
  returned `0.50413223140495867769` = 50.4% — matches the T010 ground truth
  (1037/2057).
- Expression arguments go through GraphJin role allow-list checks (per
  docs), so a non-allowlisted column cannot leak through `expr`.
- Zero-denominator: when no rows match the base filters, GraphJin returns
  `null` for the expression aggregate (avg over empty set) — the pipeline
  maps this to the stable clarification per FR-004.

**Rationale**: one validated request, one executed result, strongest
grounding (spec Q1: A). No answer-program arithmetic needed.

**Alternatives considered**:
- Two aliased `tickets_aggregate` counts in one GraphQL query + answer-side
  division — works live (verified: `breached: 1037, total: 2057`) but moves
  the final computation out of the governed layer and into the LLM-facing
  program; weaker grounding, more failure modes.
- `ratio(expr: {div: [...]})` ratio-of-aggregates form — documented, but
  requires sum/count expression nodes and is unnecessary for boolean-flag
  ratios; the `avg(case)` form is simpler and already verified.

## Decision 4: HAVING — post-aggregation filter in the application layer

**Decision**: Support `having` on grouped requests as a **deterministic
application-layer post-filter** over the returned groups, after GraphJin
execution. The validator allowlists the having shape (aggregate function +
comparison op + numeric threshold); the pipeline applies it to the executed
group rows before grounding. The trace records that filtering happened
client-side and how many groups were dropped.

**Evidence**: GraphJin v3 has no HAVING support:
- `having:` argument → "unknown argument 'having'".
- `where` on the aggregate column (`count_ticket_id`) → "column not found"
  (where is pre-aggregation).
- `expr` inside `where` → rejected ("expr is only valid on aggregate fields").
- qcode source (master) contains no having compilation path.

**Rationale**: the governed boundary (validator + read-only GraphJin) is
unchanged; the post-filter is a pure function over already-governed result
rows, cannot reach the database, and is fully testable. Result-limit
interplay is documented: GraphJin applies `limit` to groups before the
post-filter, so answers state when truncation is possible (spec edge case).

**Alternatives considered**:
- Skip HAVING in v2 — rejected: "merchants with more than 50 tickets" is an
  explicit spec user story (US1 scenario 3).
- Subquery/CTE via raw SQL — prohibited (no arbitrary SQL).

## Decision 5: Planner/signature changes are docstring-only

**Decision**: Update `ClassifyQuestion` and `PlanQuery` docstrings to
describe the new shapes (group_by, having, is_null/is_not_null, ratio) and
remove the current "NEVER emit group_by" / "no is-null operator" rules.
Extend `parse_request_json` normalization: remove `group_by`/`having` from
`_UNSUPPORTED_KEYS`, add them to `_ALLOWED_KEYS`, keep rejecting truly
unsupported shapes (joins, subqueries, union, distinct-as-key).

**Rationale**: the DSPy signatures are the instruction surface; the typed
schema + validator remain the enforcement. Optimization (if run) uses the
approved BootstrapFewShot on the extended dev set.

## Resolved clarifications

| Question | Decision | Source |
|----------|----------|--------|
| Ratio mechanism | Dedicated `ratio` aggregate in the query schema (Q1: A) | spec clarification 2026-10-10 |
| Open/closed UX | `is_null` on `closed_at` only; no derived field (Q2: A) | spec clarification 2026-10-10 |
| HAVING support | Application-layer post-filter (no GraphJin native support) | live probes + source |
| GraphQL group-by syntax | `distinct` + aggregate columns | live probes + docs |
| Ratio GraphQL syntax | `avg(expr: {case: ...})` expression aggregate | live probe, 50.4% verified |

## Risks

- **Post-filter vs. limit interplay**: a having filter can only drop groups
  from the returned page; if GraphJin truncated groups at `limit`, the
  answer must reflect possible truncation. Mitigation: trace event +
  answer-program instruction; grouped queries default `order_by` on the
  aggregate so top-N questions are exact.
- **Expression-aggregate allowlist**: GraphJin checks expr columns against
  role allow-lists; the validator additionally restricts `ratio.field` to
  boolean columns in `COLUMN_TYPES`, so no new leak path.
- **Planner regression on existing shapes**: mitigated by FR-011 (existing
  eval cases must pass unchanged) and the full pytest suite.
