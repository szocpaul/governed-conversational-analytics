# Feature Specification: Count over Content

**Feature Branch**: `[012-count-over-content]`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Answer 'how many tickets about X' (count-over-content) questions with a TRUE count of the tickets whose text matches the content query, through a governed, read-only, deterministic path. A ticket counts as a match when it matches lexically (full-text search) OR semantically (vector distance within a calibrated threshold), so deep paraphrases are counted, not just exact-word matches. The count must not undercount topics that exceed the retrieval result limit, must not change the existing structured or content paths, and must follow the feature 004 evaluation discipline (calibrated threshold on dev cases, held-out isolation, baseline comparison). See specs/012-count-over-content-sketch.md and the six human-approved decisions of 2026-10-14."

## Background

Feature 011 fixed content routing: deep-paraphrase content questions now reach governed retrieval. But manual testing surfaced a remaining gap that pre-dates 011 and is not a routing bug: "how many tickets about login" is routed to the structured path (a count), which returns 0 because "login" is not a structured column value — it lives in the ticket text. The structured path cannot express "count tickets whose text matches X", and the content path (feature 010 retrieval) returns a ranked LIST capped at MAX_RETRIEVAL_LIMIT = 25, so counting the list would undercount any topic with more than 25 matches. "How many tickets about X" is therefore a THIRD query shape that neither existing path serves.

Verified ground truths (checked directly on 2026-10-14):

- "login" appears in the text of 88 tickets; SSO Failure (the closest structured sub_category) has 90; Account Access (the category) has 360.
- The structured path can only filter on structured columns (category, sub_category, priority, ...); it cannot count by text content.
- The content retrieval path returns a ranked list capped at 25 (governed hard cap), not a count.
- The tickets table has a generated `fts` tsvector column (GIN index) and an `embedding vector(768)` column (HNSW index) from feature 010, both over the allowlisted text fields.
- Full pre-existing automated test suite: 622 tests, green.

Human-approved decisions (binding, 2026-10-14):

1. **Count semantics**: HYBRID — a ticket counts as a match when it matches lexically (`fts @@ plainto_tsquery`) OR semantically (vector distance <= a calibrated threshold). This catches deep paraphrases in the count, not just exact-word matches.
2. **Routing**: a new `content_count` category in the feature 011 classifier; the classifier learns "how many ... about X" -> content_count (consistent with one-classifier routing).
3. **Semantic threshold**: a calibrated, recorded parameter (not hardcoded); tuned on dev cases and measured on held-out cases per feature 004 discipline.
4. **Grounding**: the answer returns the count plus up to 5 example ticket_ids in the trace (capped, sanitized).
5. **Evaluation**: +5 development and +6 held-out count-over-content cases (including a security case like "how many tickets contain passwords"), in physically separate files, with zero held-out leakage.
6. **False-count guard**: the feature 011 false-routing metric is extended with the new `content_count` category; the structured execution-accuracy gate must not regress.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - True count over content via a governed hybrid count (Priority: P1)

A user asks "how many tickets about login" (or any count-over-content question, including a paraphrase like "how many tickets are about sign-in problems") and receives the TRUE count of matching tickets — counting both exact-word matches and semantic paraphrase matches — not 0 (the structured path's misleading answer) and not a capped list length. The count is computed by a governed, read-only, deterministic hybrid count query over the allowlisted text fields, and the answer grounds on the count plus a few example tickets for transparency.

**Why this priority**: This is the entire point of the feature. It closes the gap where a whole class of natural questions ("how many tickets about X") currently returns a misleading 0.

**Independent Test**: Ask "how many tickets about login" and verify it returns the true count (88, counting lexical + semantic matches), not 0 and not 25; ask a paraphrase count and verify semantic matches are included; ask a structured count ("how many P1 tickets") and verify it is unchanged. Delivers value standalone.

**Acceptance Scenarios**:

1. **Given** the governed hybrid count, **When** "how many tickets about login" is asked, **Then** it returns the true count of matching tickets (lexical + semantic), not 0 and not a capped list length.
2. **Given** a paraphrase count question such as "how many tickets are about sign-in problems", **When** the count is computed, **Then** semantic matches (tickets about authentication/SSO that do not contain the exact words) are included via the calibrated threshold.
3. **Given** a topic with few matches, **When** the count is computed, **Then** the exact small count is returned (no undercount, no cap).
4. **Given** a structured count such as "how many P1 tickets are there?", **When** it is asked, **Then** it is answered by the structured path exactly as before this feature.
5. **Given** the count answer, **When** the trace is inspected, **Then** it shows the count plus up to 5 example ticket_ids (capped, sanitized), with no credentials, endpoint details, or prompts.

---

### User Story 2 - Calibrated threshold and measured count quality under isolation (Priority: P2)

A maintainer calibrates the semantic-match threshold on labeled development cases only, measures count accuracy on the held-out set, and verifies the structured path does not regress and false-count routing is bounded. No held-out case is consumed by calibration, and the threshold is a recorded, versioned parameter — never hardcoded.

**Why this priority**: The hybrid count's quality depends on the semantic threshold, which must be calibrated and measured, not guessed. It depends on Story 1 (the count path must exist) but is independently testable through the evaluation harness.

**Independent Test**: Calibrate the threshold on dev cases; run the held-out evaluation; verify count accuracy meets the threshold, the structured execution-accuracy gate does not regress, the false-count routing rate is bounded, and zero held-out IDs appear in the calibration input.

**Acceptance Scenarios**:

1. **Given** the labeled count-over-content cases, **When** the case files are inspected, **Then** +5 development and +6 held-out cases exist in physically separate files with stable unique IDs, including a security case.
2. **Given** the dev cases, **When** threshold calibration runs, **Then** it consumes only development cases and produces a recorded, versioned threshold parameter.
3. **Given** the calibrated threshold, **When** the held-out evaluation runs (temperature zero, cache disabled), **Then** count accuracy meets the threshold, the structured execution-accuracy gate does not regress, and the false-count routing rate is bounded.
4. **Given** a security count question such as "how many tickets contain passwords", **When** it is asked, **Then** it returns nothing prohibited and the trace contains no credentials, endpoint details, or prompts.

---

### Edge Cases

- A count-over-content question with zero matches: the count is 0 (a true, grounded zero — distinguishable from the structured path's misleading 0 because the count path actually searched the text).
- A topic with more matches than the retrieval result limit (e.g. 88 login tickets vs the 25 cap): the count MUST be the true total (88), not the capped list length.
- A paraphrase count question with no exact-word matches: semantic matches within the calibrated threshold are still counted.
- A structured count question ("how many P1 tickets"): routed to the structured path unchanged — false-count routing to the content count would give a wrong answer.
- A count-over-content question mis-routed to the structured path: counted in the false-count metric and bounded by the held-out gate.
- A security count question ("how many tickets contain passwords/secrets"): returns nothing prohibited; the count mechanism does not disclose ticket content.
- The semantic threshold absent or uncalibrated: the count path MUST stop and report (no hardcoded default); it never ships an uncalibrated threshold.
- A grouped count-over-content question ("how many tickets about X per category"): out of scope for this feature; routed per the existing classifier behavior (structured or clarification).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST answer count-over-content questions ("how many tickets about X") with a TRUE count of matching tickets, computed by a governed, read-only, deterministic hybrid count query over the allowlisted text fields (the three generated text fields from feature 009).
- **FR-002**: A ticket MUST count as a match when it matches lexically (`fts @@ plainto_tsquery`) OR semantically (vector distance <= a calibrated threshold); deep paraphrase matches MUST be included, not just exact-word matches.
- **FR-003**: The count MUST be the true total of matching tickets and MUST NOT be limited by the retrieval result limit (it MUST NOT undercount topics with more matches than the retrieval cap).
- **FR-004**: The count query MUST be governed: an explicit field allowlist, the read-only database role, a parameterized query (no arbitrary SQL, the query text and threshold as bound parameters), and a sanitized trace.
- **FR-005**: The semantic-match threshold MUST be a calibrated, recorded, versioned parameter (never hardcoded); if the threshold is absent or uncalibrated, the count path MUST stop and report.
- **FR-006**: Count-over-content questions MUST be routed via a new `content_count` category in the feature 011 classifier; the existing structured and content paths MUST remain unchanged.
- **FR-007**: The count answer MUST ground on the count plus up to 5 example ticket_ids in the trace (capped, sanitized); a factual answer MUST be supported by the count result, and if evidence is absent the answer path MUST return a stable clarification (never fabricate).
- **FR-008**: Threshold calibration MUST consume development cases only; new count-over-content cases MUST be added under the feature 004 isolation discipline (at least 5 development and at least 6 held-out cases, including a security case) in physically separate files with stable unique IDs; zero held-out case IDs MUST be consumed by calibration.
- **FR-009**: Count quality MUST be measured with real runs (temperature zero, cache disabled): count accuracy on the held-out set (exact count match), the structured execution-accuracy gate (which MUST NOT regress), and a bounded false-count routing rate (the feature 011 false-routing metric extended with `content_count`).
- **FR-010**: Security count questions MUST return nothing prohibited, and the count mechanism and trace MUST NOT expose credentials, private endpoint details, complete prompts, or prohibited data.
- **FR-011**: The feature MUST NOT regress existing behavior: the full pre-existing automated test suite (622 tests) MUST pass unchanged, and structured counts and content retrieval MUST be answered exactly as before.
- **FR-012**: Grouped counts over content ("how many tickets about X per category") MUST remain out of scope; this feature is the single count only.

### Key Entities *(include if feature involves data)*

- **Content Count**: The true total of tickets whose text matches a content query (lexical OR semantic-within-threshold), computed by a governed hybrid count query. A single number, grounded with up to 5 example ticket_ids.
- **Semantic-Match Threshold**: The calibrated, recorded, versioned vector-distance parameter that defines a semantic "match" for the count; tuned on dev cases, measured on held-out cases.
- **Count-over-Content Case**: A labeled example (question, expected true count, and optionally expected matching categories) used for calibration (dev) or evaluation (held-out).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: True count: "how many tickets about login" returns the true count of matching tickets (lexical + semantic), verified against the real database — not 0 and not a capped list length.
- **SC-002**: Paraphrase count: a paraphrase count question includes semantic matches (tickets without the exact words) via the calibrated threshold.
- **SC-003**: No undercount: a topic with more matches than the retrieval result limit returns the true total, not the capped list length.
- **SC-004**: Count accuracy: the held-out count accuracy (exact count match) meets the threshold set after noise calibration.
- **SC-005**: No structured regression: the structured execution-accuracy gate does not regress, and structured counts are answered exactly as before.
- **SC-006**: Bounded false-count: the rate of count-over-content questions mis-routed (to the structured path) or structured counts mis-routed (to content count) is within the bounded value.
- **SC-007**: Evaluation isolation: +5 dev and +6 held-out cases exist in physically separate files, and zero held-out case IDs appear in any calibration input.
- **SC-008**: Security: 100% of security count questions return nothing prohibited, and traces contain no credentials, endpoint details, or prompts.
- **SC-009**: Zero regression: the full pre-existing automated test suite (622 tests) passes with no failures introduced by this feature.

## Assumptions

- The six human decisions of 2026-10-14 are binding: hybrid count (lexical OR semantic-within-threshold); a `content_count` classifier category; a calibrated, recorded threshold; count + up to 5 examples in the trace; +5 dev / +6 held-out cases; a false-count guard with no structured regression.
- The retrieval list path (feature 010), the structured planner (features 002-005), and the feature 011 classifier routing are extended, not replaced: this feature adds a count path and a routing category without changing the existing paths.
- The semantic threshold is calibrated per the feature 004 discipline (dev-only, held-out measured, noise calibration before setting gates); if calibration cannot reach the count-accuracy threshold, the run stops and reports to the human.
- Grouped counts over content are explicitly out of scope; this feature is the single count only.
- The exact threshold value, the count-accuracy and false-count thresholds, and the precise hybrid match semantics (lexical OR semantic) are plan-phase details within the approved decisions; the spec fixes only the hybrid approach and the no-undercount requirement.
