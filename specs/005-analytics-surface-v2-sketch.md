# Feature Sketch: Analytics Surface v2 (005)

**Status**: Sketch — not yet a full spec. Created from spec 004 T010 review findings.
**Depends on**: specs 001-004 complete.

## Origin

During the spec 004 T010 human review, three documented scope limits of the
StructuredQueryRequest surface were confirmed as legitimate but missing
capabilities. All three are correctness-safe today (the validator rejects or
the grounding refuses), but they block common, legitimate analytical questions.

## The three limits (verified with ground truths)

### 1. GROUP BY / HAVING aggregations
- **Blocked question**: "Which category has the most tickets?", "How many P1/P2
  tickets after 2026-01-01, grouped by category?", "Which merchants have more
  than 50 tickets, avg resolution by sector?"
- **Current**: planner emits group_by/having -> validator rejects as
  `unsupported` (correct, no SQL reaches GraphJin).
- **Ground truth examples**: top category = Payments & Checkout (483); P1=49,
  P2=163 after 2026-01-01.
- **Work**: add `group_by: list[str]` + optional `having` to the schema, extend
  build_graphql, extend validator allowlist, new eval cases.

### 2. NULL / missing-value filtering (is-null operator)
- **Blocked question**: "Show tickets where the assigned agent is missing",
  "List the 5 oldest OPEN tickets" (open = closed_at IS NULL).
- **Current**: planner emits a null filter value -> validator rejects (no
  is-null op). "Open tickets" is a common concept with no path.
- **Ground truth**: 250 tickets with assigned_agent_id IS NULL.
- **Work**: add `is_null` / `is_not_null` FilterOp, GraphQL null handling,
  validator support. Consider a derived `status: open/closed` field as an
  alternative UX for the common case.

### 3. Ratio / percentage metrics
- **Blocked question**: "What percentage of tickets breached their resolution
  SLA?"
- **Current**: planner tries avg(boolean) -> rejected; a filtered count (1037)
  runs but the ratio (1037/2057 = 50.4%) is not computed.
- **Work**: either a `ratio` aggregate (count(filtered)/count(total)) or a
  post-processing step in the answer program with grounded arithmetic.

## Constraints carried forward
- All three stay within the governed read-only surface; no arbitrary SQL.
- Validator remains the deterministic boundary; new shapes get allowlist checks.
- New capability => new eval cases in evaluation/dev_cases.json + held-out
  cases.json (versioned bump), new baseline required.
- Tests first, observed failing, per AGENTS.md.

## Out of scope (for this sketch)
- Multi-part questions (F3 pattern) — separate, larger design decision.
- Natural-language "open/closed" synonym handling beyond the derived field.
