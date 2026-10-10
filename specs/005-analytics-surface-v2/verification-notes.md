# Live Verification Notes: Analytics Surface v2

**Date**: 2026-10-10
**Stack**: PostgreSQL 16.10-alpine + GraphJin 3.21.6 (running 21h+), app on
127.0.0.1:8001 (uvicorn), pinned local llama.cpp model, temperature 0.
**Program state**: base (unoptimized) program with the v2 signatures; the
spec-004 `optimized_program.json` was moved aside to
`artifacts/optimized_program-pre-005-2026-10-10.json` because its embedded
instructions/demos taught the old "no GROUP BY" surface. T018 re-optimizes
on the extended dev set.

## T008 — US1 grouped aggregations (live)

### Q1: "Which category has the most tickets?"
- status: `answered`; answer: "Payments & Checkout"
- evidence: `{"category": "Payments & Checkout", "count_ticket_id": 483}`
  (planner chose limit 1 for the top-1 question; `groups_truncated: true`
  correctly flagged)
- executed GraphQL: `tickets(distinct: [category], order_by:
  {count_ticket_id: desc}, limit: 1) { category count_ticket_id }`
- Ground truth 483 confirmed (matches T010 review).

### Q2: "How many P1 and P2 tickets were created after 2026-01-01, grouped by category?"
- status: `answered`; per-category counts: API Integrations 52, Payments &
  Checkout 42, Fulfilment & Logistics 35, Account Access 48, Notifications 35
- Sum = 212, consistent with the ground truth P1 = 49 + P2 = 163 = 212.
- `groups_truncated: false` (5 groups < limit 100).

### Q3: "Which merchants have more than 50 tickets?" (having)
- status: `clarification` — "No groups match the requested aggregate
  threshold." This is CORRECT for the pinned dataset: the maximum tickets
  per merchant is 32 (verified directly via GraphJin: top group
  `merchant_id 117, count 32`; 112 merchants total).
- evidence: `having_applied: {function: count, op: gt, value: 50,
  groups_dropped: 100}`, `groups_truncated: true` (100 of 112 groups
  returned at the limit; ordered by count desc so the top-100 contains
  every merchant with the highest counts — the zero-match conclusion is
  exact, not truncated).
- The spec scenario illustrates the having SHAPE; ">50" is not a labeled
  ground truth. Verified the filter mechanics end-to-end.

### Q3b (positive path): "Which merchants have more than 25 tickets?"
- status: `answered`; 9 merchants retained (ids 132, 168, 101, 117, 147,
  136, 139, 160, 106 with counts 26-32), `groups_dropped: 91`.
- Confirms the post-filter keeps matching groups and the answer is grounded
  in the retained rows.

## T011 — US2 missing-value filtering (live)

### Q1: "How many tickets have no assigned agent?"
- status: `answered`; answer: "250"
- evidence: `aggregate: {"count": 250}` — matches the ground truth exactly.
- executed: `tickets_aggregate(where: {assigned_agent_id: {is_null: true}})`.

### Q2: "List the 5 oldest open tickets"
- status: `answered`; 5 rows returned, ALL with `closed_at: null`, ordered
  by `created_at` ascending: 849061 (2026-06-29T00:25:03), 849229
  (00:47:32), 849153 (00:53:36), 849068 (00:57:56), 849250 (01:14:35).
- "open" mapped to `closed_at is_null` by the planner per the updated
  PlanQuery signature (FR-010); no derived status field involved.

## T014 — US3 ratio/percentage metrics (live)

### Q1: "What percentage of tickets breached their resolution SLA?"
- status: `answered`; answer: "50.4% of tickets breached their resolution
  SLA."
- evidence: `aggregate: {"ratio_resolution_breached":
  0.5041322314049587}` — exactly 1037/2057, the T010 ground truth.
- executed GraphQL: `tickets { ratio_resolution_breached: avg(expr:
  {case: {arms: [{when: {resolution_breached: {eq: true}}, then: 1.0}],
  else: 0.0}}) }` — one validated request, one executed result.
- Answer-side grounding: `is_grounded` now treats a `ratio_*` fraction in
  evidence as grounding its percentage form (0.5041... grounds "50.4");
  a null ratio grounds no percentage claim at all (FR-004).

Note: the first attempt was refused as ungrounded ("50.4" not literally in
evidence) before the grounding fix; after the fix the grounded answer is
returned. Zero-denominator behavior (null ratio -> stable clarification)
is covered by tests/test_pipeline_ratio.py::test_zero_denominator_gives_clarification.
