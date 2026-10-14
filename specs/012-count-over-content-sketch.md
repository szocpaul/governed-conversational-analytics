# Feature Sketch: Count over Content (012)

**Status**: Sketch — NOT yet a spec. Human review requested before any
`/speckit-specify`. Created 2026-10-14 after feature 011 (classifier-based
content routing) surfaced a pre-existing limitation in live testing.
**Depends on**: specs 001-006, 008, 009, 010, 011 complete.

## Origin (from live testing of feature 011 on 2026-10-14)

Feature 011 fixed content routing: deep-paraphrase content questions now
reach governed retrieval. But manual testing surfaced a remaining gap that
PRE-DATES 011 and is NOT a routing bug:

```
"how many tickets about login"  ->  classified: supported (structured)
                                ->  structured count = 0
```

The structured path can only filter on STRUCTURED columns (category,
sub_category, priority, ...). "login" is not a structured value — it lives
in the ticket TEXT. So the structured count returns 0, which is technically
correct for the structured query but semantically wrong for the user, who
means the 88 tickets whose text mentions "login".

Verified ground truths (2026-10-14):

- "login" appears in the text of 88 tickets; SSO Failure (the closest
  structured sub_category) has 90; Account Access (the category) has 360.
- The structured path cannot express "count tickets whose text matches X".
- The content path (feature 010 retrieval) returns a RANKED LIST, not a
  count, and is capped at MAX_RETRIEVAL_LIMIT = 25 — so "how many tickets
  about X" CANNOT be answered by counting the retrieval list (it would
  undercount any topic with more than 25 matching tickets).

So "how many tickets about X" is a THIRD query shape that neither the
structured path nor the content path currently serves:

| Question | Today | Needed |
|---|---|---|
| "tickets about login" | content -> list (capped at 25) | OK as a list |
| "how many tickets" | structured -> 2057 | OK |
| "how many tickets about login" | structured -> 0 (misleading) | count over content (88) |

## Goal

Answer "how many tickets about X" (and similar count-over-content
questions) with a TRUE count of the tickets whose text matches the content
query, through a governed, read-only, deterministic path — without
undercounting topics that exceed the retrieval result limit, and without
changing the existing structured or content paths.

## The core design problem: a true count, not a capped list

The retrieval list is capped at 25 for good governance reasons (context
size, trace hygiene). A count-over-content capability must count ALL
matching tickets, not just the top-25. Two broad approaches:

- **(A) Database-side count**: a governed, parameterized COUNT query over
  the same allowlisted text fields used by retrieval — e.g. lexical
  `COUNT(*) WHERE fts @@ plainto_tsquery(...)` and/or a semantic count over
  a vector-distance threshold. Deterministic, read-only, no result-limit
  problem. The semantic side needs a distance THRESHOLD (what counts as a
  "match"), which is a tunable, measurable parameter.
- **(B) Retrieval-then-count**: run retrieval and count the list — REJECTED
  because the list is capped at 25 and would undercount (88 login tickets
  would report 25).

Recommendation: (A) — a governed count query, mirroring the retrieval
channel's guarantees (allowlist, read-only role, parameterized, sanitized
trace). Confirm.

## Open decisions (need human input before spec)

1. **Count semantics**: what counts as a "match" for the count? (a) lexical
   only (`fts @@ plainto_tsquery`) — deterministic, no threshold, but
   misses pure-semantic paraphrases; (b) semantic only (vector distance <=
   threshold) — catches paraphrases but needs a calibrated threshold; (c)
   hybrid (lexical OR semantic-within-threshold) — best recall but two
   mechanisms to calibrate. Recommendation: start with (a) lexical for a
   deterministic, threshold-free count, and treat semantic count as a
   follow-up IF lexical proves insufficient — OR go straight to (c) if you
   want paraphrase counts now. Confirm which.
2. **Routing**: how does "how many tickets about X" reach the count path?
   The 011 classifier currently routes it to `supported` (structured). (a)
   add a new category `content_count` to the classifier, or (b) detect the
   count-over-content shape deterministically (count keyword + about/topic)
   before the classifier. Recommendation: (a) — consistent with 011's
   one-classifier routing; the classifier learns "how many ... about X" ->
   content_count. Confirm.
3. **Semantic threshold (only if 1=(b) or (c))**: the vector-distance
   threshold that defines a "match" must be calibrated on dev cases and
   measured on held-out cases (feature 004 discipline). Confirm the
   threshold is a calibrated, recorded parameter (not hardcoded).
4. **Grounding the answer**: the count is a single number; the answer
   should ground on it AND optionally show a few example tickets (top-N
   from the same governed query) for transparency. Recommendation: return
   the count plus up to N (e.g. 5) example ticket_ids in the trace, capped
   and sanitized. Confirm.
5. **Evaluation**: new dev/held-out cases for count-over-content per
   feature 004 discipline (physically separate, no leakage). Proposal: +5
   dev, +6 held-out (incl. a security case like "how many tickets contain
   passwords"). Confirm counts.
6. **False-count guard**: how to bound the risk that a count-over-content
   question is mis-routed to the structured path (returning a misleading 0)
   or that a structured count is mis-routed to content-count. Recommendation:
   extend the 011 false-routing metric with the new category; the structured
   execution-accuracy gate must not regress. Confirm.

## Testing & quality gates (proposed)

- Unit: count query construction (parameterized, no arbitrary SQL),
  allowlist enforcement, threshold validation (if semantic), routing of
  "how many tickets about X" to the count path.
- Integration: "how many tickets about login" returns 88 (the true count),
  not 0 and not 25; a topic with few matches returns the exact small count;
  structured counts ("how many P1 tickets") unchanged; security count cases
  return nothing prohibited.
- Evaluation: count accuracy on labeled cases (exact count match);
  false-routing bounded; structured gate not regressed.
- Regression: full pytest suite green (currently 622).

## Out of scope (this feature)

- Changes to the retrieval LIST path (feature 010) or the structured
  planner (features 002-005) — both frozen.
- Grouped counts over content ("how many tickets about X per category") —
  a possible follow-up; this feature is the single count only.
- Semantic count threshold tuning as a large optimization — if 1=(a), the
  first version is lexical-only and deterministic.
- UI changes.

## Rough size estimate

A governed count query (mirroring the retrieval channel), a classifier
category addition + routing, optional threshold calibration, +5 dev / +6
held-out cases, ~10-12 tests. Smaller than feature 011.

## Resolved decisions (human-approved 2026-10-14)

1. **Count semantics**: (c) HYBRID — a ticket counts as a match when it
   matches lexically (`fts @@ plainto_tsquery`) OR semantically (vector
   distance <= a calibrated threshold). This catches deep paraphrases in the
   count, not just exact-word matches.
2. **Routing**: (a) — a new `content_count` category in the 011 classifier;
   the classifier learns "how many ... about X" -> content_count (consistent
   with one-classifier routing).
3. **Semantic threshold**: a calibrated, recorded parameter (not hardcoded);
   tuned on dev cases and measured on held-out cases per feature 004
   discipline.
4. **Grounding**: the answer returns the count plus up to 5 example
   ticket_ids in the trace (capped, sanitized).
5. **Evaluation**: +5 dev and +6 held-out count-over-content cases (incl. a
   security case like "how many tickets contain passwords"), physically
   separate files, no held-out leakage.
6. **False-count guard**: the 011 false-routing metric is extended with the
   new `content_count` category; the structured execution-accuracy gate must
   not regress.

