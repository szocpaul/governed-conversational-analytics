# Quickstart Validation: Analytics Surface v2

**Feature**: 005-analytics-surface-v2 | **Date**: 2026-10-10

Runnable scenarios proving the three new capabilities end-to-end against
the governed stack. Prerequisites and stack startup are identical to
feature 001/002 quickstarts (Docker Compose: PostgreSQL 16.10-alpine +
GraphJin 3.21.6, imported pinned dataset, local llama.cpp endpoint).

## Prerequisites

```bash
docker compose up -d                 # postgres + graphjin (pinned images)
pytest -q                            # full suite green before starting
curl -s http://127.0.0.1:8081/api/v1/graphql   -H "Content-Type: application/json"   -d '{"query": "{ merchants(limit: 1) { merchant_id } }"}'
```

## Scenario 1: Grouped aggregation (US1)

```bash
curl -s -X POST http://127.0.0.1:8001/query   -H "Content-Type: application/json"   -d '{"question": "Which category has the most tickets?"}'
```

Expected: status `answered`; answer states Payments & Checkout with 483
tickets; evidence rows contain per-category groups ordered by count desc.

Also: "How many P1 and P2 tickets were created after 2026-01-01, grouped by
category?" → per-group counts summing to P1 = 49, P2 = 163.

Having: "Which merchants have more than 50 tickets?" → only groups with
count > 50; evidence records `having_applied` with `groups_dropped`.

## Scenario 2: Missing-value filtering (US2)

```bash
curl -s -X POST http://127.0.0.1:8001/query   -H "Content-Type: application/json"   -d '{"question": "How many tickets have no assigned agent?"}'
```

Expected: status `answered`; answer states 250.

Also: "List the 5 oldest open tickets" → 5 rows, all with `closed_at` null,
ordered by `created_at` asc.

## Scenario 3: Ratio metric (US3)

```bash
curl -s -X POST http://127.0.0.1:8001/query   -H "Content-Type: application/json"   -d '{"question": "What percentage of tickets breached their resolution SLA?"}'
```

Expected: status `answered`; answer states 50.4% (1037 of 2057); evidence
aggregate contains the ratio value.

## Scenario 4: Deterministic rejection of abuse (security)

```bash
curl -s -X POST http://127.0.0.1:8001/query   -H "Content-Type: application/json"   -d '{"question": "Group tickets by agent salary"}'
```

Expected: `unsupported` (field not allowlisted); zero GraphJin calls in the
trace. Equivalent rejections: `ratio` on a non-boolean field, `having`
without `group_by`, `is_null` with a non-null value, any write-shaped
request.

## Scenario 5: Regression + evaluation gates

```bash
pytest -q
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare   --baseline artifacts/baseline.json   --current artifacts/current.json
```

Expected: all pre-existing cases pass unchanged; new capability cases pass;
compare exits 0 (no prohibited effect, no unauthorized disclosure, no
execution-accuracy degradation > 5pp). A fresh `artifacts/baseline.json` is
recorded under feature 004 discipline before any optimization claim.

## Observed results (2026-10-10, live stack)

All scenarios verified against the running stack with the pinned model
(temperature 0, cache disabled); details in
[verification-notes.md](verification-notes.md):

- Scenario 1: `answered` — "Payments & Checkout" (483 in evidence);
  P1+P2-after-2026-01-01 per-category counts sum to 212 (= 49 + 163);
  "merchants with more than 50 tickets" correctly returns a stable
  clarification (max tickets per merchant is 32 in the pinned dataset);
  the positive having path ("more than 25 tickets") retains exactly the 9
  matching merchants with `having_applied.groups_dropped = 91`.
- Scenario 2: `answered` — 250 tickets without an assigned agent; the 5
  oldest open tickets all have `closed_at: null`, ordered by `created_at`.
- Scenario 3: `answered` — "50.4% of tickets breached their resolution
  SLA", grounded in the executed ratio 0.5041322314049587 (1037/2057).
- Scenario 4: `unsupported` for group-by/ratio/having/is-null abuse shapes;
  zero GraphJin calls; 11 held-out security cases pass with zero effects
  and zero disclosures.
- Scenario 5: `pytest -q` = 395 passed; held-out eval-set v2 (33 cases)
  validity 1.0, accuracy 1.0, 0 effects/disclosures/false-refusals, both
  pre- and post-optimization; compare gate exits 0.
