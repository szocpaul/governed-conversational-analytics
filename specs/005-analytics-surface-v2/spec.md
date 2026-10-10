# Feature Specification: Analytics Surface v2

**Feature Branch**: `[005-analytics-surface-v2]`

**Created**: 2026-10-10

**Status**: Approved

**Input**: User description: "Extend the governed conversational analytics query surface with three capabilities identified as missing during the spec 004 T010 human review: (1) GROUP BY / HAVING aggregations (e.g. 'Which category has the most tickets?'), (2) NULL / missing-value filtering via an is-null operator (e.g. 'Show tickets where the assigned agent is missing', 'List the 5 oldest OPEN tickets'), and (3) ratio / percentage metrics (e.g. 'What percentage of tickets breached their resolution SLA?'). All three must stay within the governed read-only surface: no arbitrary SQL, the deterministic validator remains the boundary, and every new capability ships with new evaluation cases and a new baseline. See specs/005-analytics-surface-v2-sketch.md."

## Background (Diagnosis)

During the spec 004 T010 human review, three documented scope limits of the structured query request surface were confirmed as legitimate but missing capabilities. All three are correctness-safe today — the validator rejects the request or the grounding refuses to answer — but they block common, legitimate analytical questions. Verified ground truths from the pinned dataset:

- Top ticket category by count: Payments & Checkout (483 tickets); P1 = 49, P2 = 163 tickets after 2026-01-01.
- 250 tickets have a missing assigned agent.
- 1037 of 2057 tickets breached their resolution SLA (50.4%).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Grouped Aggregations (Priority: P1)

An analyst asks questions like "Which category has the most tickets?" or "How many P1/P2 tickets were created after 2026-01-01, grouped by category?" and receives a grouped breakdown with per-group counts or aggregates, instead of a refusal.

**Why this priority**: Grouped breakdowns are the most common analytical pattern blocked today; they were the first documented gap from the T010 review and have verified ground truths.

**Independent Test**: Ask "Which category has the most tickets?" and verify the answer reports Payments & Checkout with 483 tickets, supported by an executed grouped query result.

**Acceptance Scenarios**:

1. **Given** the governed query pipeline, **When** the user asks "Which category has the most tickets?", **Then** the system executes a validated grouped aggregation and answers that Payments & Checkout has the most tickets (483), grounded in the returned groups.
2. **Given** the governed query pipeline, **When** the user asks "How many P1 and P2 tickets were created after 2026-01-01, grouped by category?", **Then** the answer reports per-category counts consistent with the executed result (P1 = 49, P2 = 163 in total).
3. **Given** a grouped request with a group filter such as "merchants with more than 50 tickets", **When** the request is planned, **Then** the system validates and executes it with a post-aggregation filter and answers only from the returned groups.
4. **Given** a grouped request that references a field outside the governed allowlist, **When** the request is validated, **Then** it is rejected deterministically and no database query is executed.

---

### User Story 2 - Missing-Value Filtering (Priority: P1)

An analyst asks "Show tickets where the assigned agent is missing" or "List the 5 oldest open tickets" and receives the matching records, where "open" means the ticket has no closing timestamp.

**Why this priority**: "Open tickets" is a core operational concept with no current query path; missing-value filtering is also required for data-quality questions. Both were confirmed blocked with a verified ground truth (250 tickets without an assigned agent).

**Independent Test**: Ask "How many tickets have no assigned agent?" and verify the answer reports 250, supported by an executed is-null filtered count.

**Acceptance Scenarios**:

1. **Given** the governed query pipeline, **When** the user asks "How many tickets have no assigned agent?", **Then** the system executes a validated missing-value filtered count and answers 250.
2. **Given** the governed query pipeline, **When** the user asks "List the 5 oldest open tickets", **Then** the system returns the 5 oldest tickets that have no closing timestamp, ordered by creation time.
3. **Given** a request filtering on the presence of a value (e.g. "tickets that have been closed"), **When** validated and executed, **Then** only records where the field is present are returned.
4. **Given** a missing-value filter on a field outside the governed allowlist, **When** the request is validated, **Then** it is rejected deterministically and no database query is executed.

---

### User Story 3 - Ratio and Percentage Metrics (Priority: P2)

An analyst asks "What percentage of tickets breached their resolution SLA?" and receives a single percentage figure grounded in executed counts, instead of a refusal or an ungrounded number.

**Why this priority**: Ratio questions are common business questions but slightly less frequent than grouped breakdowns; the component counts are already obtainable, so the incremental value is the grounded ratio itself.

**Independent Test**: Ask "What percentage of tickets breached their resolution SLA?" and verify the answer reports 50.4% (1037 of 2057), with both counts visible in the executed evidence.

**Acceptance Scenarios**:

1. **Given** the governed query pipeline, **When** the user asks "What percentage of tickets breached their resolution SLA?", **Then** the system obtains the breached count (1037) and the total count (2057) through validated requests and answers 50.4%, with the arithmetic traceable to the executed results.
2. **Given** a ratio question whose denominator count is zero, **When** the system computes the ratio, **Then** it answers with a stable clarification that the ratio is undefined instead of fabricating a number.
3. **Given** any ratio answer, **When** the trace is inspected, **Then** the numerator and denominator each come from an executed governed result and no number appears without evidence.

---

### Edge Cases

- A grouped aggregation combined with a missing-value filter (e.g. "open tickets per category") MUST compose correctly within one validated request where the surface allows it.
- A group-by field with high cardinality MUST still respect the governed result limit; the answer MUST reflect only the returned groups and say so when truncation is possible.
- A ratio whose filtered count equals the total count MUST report 100% rather than failing.
- Requests that try to use the new operators to reach fields or operations outside the governed allowlist MUST be rejected deterministically with zero database effect.
- Answers for the new capabilities MUST follow the same grounding rule as existing ones: no executed evidence, no factual claim.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The query surface MUST accept grouped aggregation requests: one or more grouping fields combined with an aggregate function, within the governed entity/field allowlist.
- **FR-002**: The query surface MUST accept an optional post-aggregation group filter (having) on grouped aggregation requests, within the governed allowlist.
- **FR-003**: The query surface MUST accept missing-value filters (is-null and is-not-null) on governed fields.
- **FR-004**: The query surface MUST accept a dedicated ratio aggregate that computes count(filtered)/count(total) within a single validated request, so that ratio/percentage answers are grounded in one executed governed result. A zero denominator MUST produce a stable clarification, not a fabricated number.
- **FR-005**: The deterministic validator MUST remain the boundary for all new request shapes: every new field, operator, and shape MUST be explicitly allowlisted, and any non-conforming request MUST be rejected before any database access.
- **FR-006**: All new capabilities MUST remain read-only; INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER, and DROP MUST remain impossible through the runtime query path.
- **FR-007**: Answers using the new capabilities MUST be grounded in executed results; if evidence is absent, ambiguous, or unavailable, the system MUST return a stable clarification, refusal, or dependency error.
- **FR-008**: The development and held-out evaluation sets MUST gain new versioned cases covering each new capability, including security/unauthorized-access cases that attempt to abuse the new operators; held-out isolation rules from feature 004 remain in force.
- **FR-009**: A new baseline MUST be recorded after the surface extension, following the feature 004 baseline discipline (temperature zero, cache disabled, repeated sample, pinned metadata).
- **FR-010**: Open vs. closed tickets MUST be queryable through the missing-value filter on the closing timestamp (open = closed_at is null); no derived open/closed status field is added to the governed surface in this feature.
- **FR-011**: Existing evaluation cases MUST continue to pass unchanged after the extension (no regression in current behavior).

### Key Entities *(include if feature involves data)*

- **Structured query request**: the typed, validated request shape exchanged between planner, validator, and governed data access; gains grouping, post-aggregation filtering, and missing-value filtering dimensions.
- **Grouped result**: a set of groups, each with its grouping field values and aggregate value; subject to the governed result limit.
- **Ratio evidence**: the pair of executed counts (numerator, denominator) that grounds a percentage answer.
- **Evaluation case**: versioned labeled example with stable ID; new cases cover the new capabilities in both development and held-out sets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the verified ground-truth questions from the T010 review are answered correctly: top category Payments & Checkout (483), P1 = 49 and P2 = 163 after 2026-01-01, 250 tickets without an assigned agent, 50.4% SLA breach ratio.
- **SC-002**: 100% of requests using new operators on non-allowlisted fields or non-read-only operations are rejected deterministically with zero database effect.
- **SC-003**: 100% of answers for the new capabilities are grounded in executed results; zero fabricated numbers in evaluation.
- **SC-004**: All pre-existing evaluation cases (development and held-out) pass unchanged after the extension.
- **SC-005**: New evaluation coverage adds each new capability to both the development and held-out sets, with at least 5 held-out security/unauthorized-access cases maintained and held-out isolation preserved (zero held-out IDs consumed by optimization).
- **SC-006**: A new baseline artifact is recorded under the feature 004 discipline, and the comparison gate passes with no prohibited effect, no unauthorized disclosure, and no execution-accuracy degradation greater than 5 percentage points.

## Assumptions

- Features 001-004 remain complete and unchanged in behavior; this feature extends the existing surface rather than replacing it.
- The pinned dataset and its verified ground truths (483 top category, 49/163 priority counts, 250 missing agents, 1037/2057 SLA breach) remain the reference for new evaluation cases.
- Multi-part questions (the F3 pattern from the T010 review) remain out of scope; they require a separate, larger design decision.
- Natural-language synonym handling for open/closed beyond the chosen approach in FR-010 is out of scope.
- Optimization, if run, uses only the approved BootstrapFewShot configuration from feature 004 and only development examples.

## Out of Scope

- Multi-part / multi-intent questions.
- Arbitrary SQL or any relaxation of the governed read-only boundary.
- New entities or data source changes.
- Latency targets (latency remains observational only).

## MANUAL GATE 1: Specification Review

- **Approved**
