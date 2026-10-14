# Feature Specification: Classifier-Based Content Routing

**Feature Branch**: `[011-classifier-content-routing]`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Replace the narrow regex-based content-question router with a tuned, meaning-based DSPy classifier so that content questions — including deep paraphrases with zero shared keywords — are routed to governed hybrid retrieval, while structured analytical questions keep going to the structured path unchanged and unsupported/out-of-scope questions are still refused. The routing decision must be measurable (routing accuracy on labeled cases), must not degrade the structured path (false-routing measured and bounded), and must follow the feature 004 evaluation discipline (BootstrapFewShot on dev cases only, held-out isolation, baseline comparison). See specs/011-classifier-content-routing-sketch.md and the seven human-approved decisions of 2026-10-14."

## Background

Feature 010 delivered governed hybrid retrieval, and the retrieval motor is excellent: when a content question reaches it, results are highly relevant (verified live on 2026-10-14: "similar to ticket 847204" returned all Endpoint Timeout tickets; "3DS authentication prompt timing out during checkout" returned all 3DS Authentication tickets). However, the content-question ROUTER is a narrow deterministic regex pair in `app/api/routes.py` (`_ABOUT_RE`, `_SIMILAR_RE`) that decides routing by word shape, not meaning. Live testing confirmed that deep paraphrase content questions — "Which tickets describe customers unable to complete a purchase because their card was rejected?", "locked out, can't prove who you are at sign-in", "slow to notify users" — never reach retrieval: they miss the regex trigger and fall through to the structured classifier, which returns "supported" (GraphJin, 0 rows) or "unsupported" (refusal). The retrieval embedding already handles paraphrase well; the problem is the question never reaches it.

Verified ground truths (checked directly on 2026-10-14):

- The content router is a deterministic regex pair in `app/api/routes.py` (`_route_content_question`), running BEFORE the DSPy `ClassifyQuestion`.
- The DSPy `ClassifyQuestion` (pinned Qwen3) currently outputs `supported` / `ambiguous` / `unsupported` for the structured path only.
- The retrieval embedding (EmbeddingGemma-2) already maps paraphrases near their targets (feature 010 verified).
- Full pre-existing automated test suite: 571 tests, green.
- Evaluation corpora are physically separate: `evaluation/dev_cases.json` (25 cases), `evaluation/cases.json` (41 held-out cases).

Human-approved decisions (binding, 2026-10-14):

1. **Router mechanism**: extend the existing DSPy `ClassifyQuestion` with `content_about` and `content_similar` categories so ONE classifier routes everything; the regex router (`_ABOUT_RE`, `_SIMILAR_RE`, `_route_content_question`) is removed.
2. **Tuning method**: BootstrapFewShot (the only AGENTS.md-approved optimizer), on development cases only. If it does NOT reach the routing-accuracy threshold, STOP AND REPORT to the human; GEPA/MIPROv2/SIMBA remain forbidden unless the human amends AGENTS.md.
3. **Dev/held-out case counts**: +8 development routing cases and +10 held-out routing cases (a mix of content_about, content_similar, structured, unsupported, including deep paraphrases and security cases), in physically separate files, with zero held-out leakage.
4. **False-routing guard**: a held-out metric "structured questions routed to the structured path >= X%" plus the structured execution-accuracy gate must not regress; the exact threshold is set in the plan after a noise calibration run.
5. **Similar-mode ticket_id extraction**: a deterministic ticket_id extractor (the reference is a number, easy and reliable); the classifier decides the mode only.
6. **Fallback on classifier uncertainty**: conservative default to the structured path (a missed content question yields a clarification, not a wrong answer).
7. **Latency budget**: with decision 1 there is NO extra model call — the same classifier call now also routes content questions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Meaning-based content routing via a tuned classifier (Priority: P1)

A user asks a content question in natural language — including a deep paraphrase such as "Which tickets describe customers unable to complete a purchase because their card was rejected?" or "show me cases where people get locked out and can't prove who they are at sign-in" — and the tuned classifier recognizes it as a content question and routes it to governed retrieval, which returns relevant tickets. The same classifier routes structured analytical questions ("how many P1 tickets") to the structured path unchanged, and refuses unsupported/out-of-scope questions.

**Why this priority**: This is the entire point of the feature. The retrieval motor (feature 010) already works; the only gap is that deep paraphrase content questions never reach it. Fixing the routing unlocks the full value of hybrid search.

**Independent Test**: Ask a set of deep paraphrase content questions and verify they route to governed retrieval and return relevant tickets; ask structured analytical questions and verify they route to the structured path exactly as before; ask unsupported questions and verify they are still refused. Delivers value standalone (routing works end-to-end).

**Acceptance Scenarios**:

1. **Given** the tuned classifier, **When** a deep paraphrase content question such as "customers unable to complete a purchase because their card was rejected" is asked, **Then** it is classified as content_about and routed to governed retrieval, returning relevant Card Declines tickets.
2. **Given** the tuned classifier, **When** a similarity question such as "tickets similar to 847207" is asked, **Then** it is classified as content_similar, the reference ticket_id is extracted deterministically, and similar tickets are returned.
3. **Given** the tuned classifier, **When** a structured analytical question such as "how many P1 tickets are there?" is asked, **Then** it is classified as supported and routed to the structured path exactly as before this feature.
4. **Given** the tuned classifier, **When** an unsupported or out-of-scope question is asked, **Then** it is refused with a stable category, exactly as before.
5. **Given** a question the classifier is uncertain about, **When** routing is decided, **Then** it conservatively defaults to the structured path (a missed content question yields a clarification, not a wrong answer).

---

### User Story 2 - Measured tuning under dataset isolation (Priority: P2)

A maintainer tunes the classifier with BootstrapFewShot on labeled development routing cases only, measures routing accuracy on the held-out set, and verifies the structured path does not regress. No held-out case is consumed by tuning, and if BootstrapFewShot does not reach the routing-accuracy threshold, the run stops and reports to the human rather than silently shipping a degraded router.

**Why this priority**: Routing quality must be measured, not assumed, and tuning must not leak held-out data or degrade the proven structured path. It depends on Story 1 (the classifier must exist) but is independently testable through the evaluation harness.

**Independent Test**: Run BootstrapFewShot on the dev routing cases; run the held-out evaluation; verify routing accuracy meets the threshold, the structured execution-accuracy gate does not regress, the false-routing rate is bounded, and zero held-out IDs appear in the tuning input.

**Acceptance Scenarios**:

1. **Given** the labeled routing cases, **When** the case files are inspected, **Then** +8 development and +10 held-out routing cases exist in physically separate files with stable unique IDs, covering content_about, content_similar, structured, and unsupported (including deep paraphrases and security cases).
2. **Given** the dev routing cases, **When** BootstrapFewShot tuning runs, **Then** it consumes only development cases and produces a tuned classifier artifact with recorded provenance (optimizer config, accepted demo IDs, artifact hash).
3. **Given** the tuned classifier, **When** the held-out evaluation runs (temperature zero, cache disabled), **Then** routing accuracy meets the threshold, the structured execution-accuracy gate does not regress, and the false-routing rate is within the bounded value.
4. **Given** BootstrapFewShot does not reach the routing-accuracy threshold, **When** the run completes, **Then** it stops and reports to the human; it does not silently ship a degraded router, and GEPA/MIPROv2/SIMBA are not used.

---

### Edge Cases

- A deep paraphrase content question with zero shared keywords with any ticket: the tuned classifier MUST route it to retrieval (this is the core improvement).
- A structured analytical question phrased loosely ("how many tickets are about login"): the classifier MUST still route it to the structured path (count), not retrieval — false-routing to retrieval would give a wrong answer shape.
- A similarity question without the word "ticket" ("tickets similar to 847207" or just "similar to 847207"): the deterministic ticket_id extractor MUST still find the reference id.
- A similarity question with a non-existent ticket_id: retrieval returns no evidence and the answer path returns a stable clarification (never fabricates).
- A security content question ("retrieve tickets containing passwords/secrets"): MUST return nothing prohibited, and the trace MUST contain no credentials, endpoint details, or prompts.
- A question the classifier cannot confidently route: conservative default to the structured path.
- An ambiguous multi-part question: classified as ambiguous and asked for clarification, exactly as before.
- BootstrapFewShot fails to reach the routing-accuracy threshold: the run MUST stop and report to the human; it MUST NOT ship a degraded router or fall back to GEPA/MIProV2/SIMBA.
- A structured question mis-routed to retrieval: counted in the false-routing metric and bounded by the held-out gate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The content-question router MUST be a tuned DSPy classifier (the existing `ClassifyQuestion` extended with `content_about` and `content_similar` categories) so that ONE classifier routes every question; the deterministic regex router (`_ABOUT_RE`, `_SIMILAR_RE`, `_route_content_question`) MUST be removed.
- **FR-002**: The classifier MUST route content questions — including deep paraphrases with zero shared keywords — to governed retrieval (mode=about or mode=similar), MUST route structured analytical questions to the structured path unchanged, and MUST refuse unsupported/out-of-scope questions with a stable category.
- **FR-003**: For content_similar questions, the reference ticket_id MUST be extracted by a deterministic extractor; the classifier decides the mode only and is not responsible for id extraction.
- **FR-004**: When the classifier is uncertain, routing MUST conservatively default to the structured path (a missed content question yields a clarification, not a wrong answer).
- **FR-005**: Routing MUST NOT add a model call beyond the existing classifier call (the same call now also routes content questions); latency remains observational only.
- **FR-006**: Tuning MUST use BootstrapFewShot (the only AGENTS.md-approved optimizer) on development cases only; GEPA/MIPROv2/SIMBA MUST NOT be used.
- **FR-007**: New labeled routing cases MUST be added under the feature 004 isolation discipline: at least 8 development cases and at least 10 held-out cases (covering content_about, content_similar, structured, and unsupported, including deep paraphrases and security cases) in physically separate files with stable unique IDs; zero held-out case IDs MUST be consumed by tuning.
- **FR-008**: Routing quality MUST be measured with real runs (temperature zero, cache disabled): routing accuracy on the held-out set, the structured execution-accuracy gate (which MUST NOT regress), and a bounded false-routing rate (structured questions mis-routed to retrieval).
- **FR-009**: If BootstrapFewShot does NOT reach the routing-accuracy threshold, the run MUST stop and report to the human; it MUST NOT silently ship a degraded router.
- **FR-010**: A tuned classifier artifact MUST be pinned, versioned, SHA-256-checksummed, and recorded with provenance (optimizer config, accepted demo IDs, artifact hash), following the existing optimized-program artifact discipline.
- **FR-011**: The retrieval path and the structured query path themselves MUST NOT change; only the routing decision changes.
- **FR-012**: Security content questions MUST return nothing prohibited, and the retrieval trace MUST NOT expose credentials, private endpoint details, complete prompts, or prohibited data.
- **FR-013**: The feature MUST NOT regress existing behavior: the full pre-existing automated test suite (571 tests) MUST pass unchanged, and structured analytical questions MUST be answered exactly as before.

### Key Entities *(include if feature involves data)*

- **Routing Decision**: The output of the tuned classifier for one question — a category (content_about, content_similar, structured, unsupported, ambiguous) plus, for content_similar, a deterministically extracted reference ticket_id. Determines which governed path handles the question.
- **Routing Case**: A labeled example (question, expected routing category, and for content cases the expected relevant ticket set or reference ticket_id) used for tuning (dev) or evaluation (held-out).
- **Tuned Classifier Artifact**: The pinned, versioned, SHA-256-checksummed output of one BootstrapFewShot tuning run, with recorded provenance (optimizer config, accepted demo IDs, artifact hash).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Deep paraphrase routing: a measured set of deep paraphrase content questions (zero shared keywords with their target tickets) route to governed retrieval and return relevant tickets — verified against the real database.
- **SC-002**: Routing accuracy: the held-out routing accuracy meets the threshold set after noise calibration (recorded in the evaluation artifact).
- **SC-003**: No structured regression: the structured execution-accuracy gate on the held-out set does not regress, and structured analytical questions are answered exactly as before this feature.
- **SC-004**: Bounded false-routing: the rate of structured questions mis-routed to retrieval is within the bounded value set after noise calibration.
- **SC-005**: Evaluation isolation: +8 dev and +10 held-out routing cases exist in physically separate files, and zero held-out case IDs appear in any tuning input.
- **SC-006**: Tuning discipline: tuning uses BootstrapFewShot on dev cases only; if the threshold is not reached, the run stops and reports to the human (no degraded router, no GEPA/MIPROv2/SIMBA).
- **SC-007**: Security: 100% of security content questions return nothing prohibited, and traces contain no credentials, endpoint details, or prompts.
- **SC-008**: Zero regression: the full pre-existing automated test suite (571 tests) passes with no failures introduced by this feature.

## Assumptions

- The seven human decisions of 2026-10-14 are binding: one extended classifier (regex removed); BootstrapFewShot with stop-and-report if insufficient; +8 dev / +10 held-out cases; false-routing guard with a calibrated threshold; deterministic ticket_id extraction; conservative fallback; no extra model call.
- The retrieval motor (feature 010) and the structured query planner (PlanQuery) are complete and frozen; this feature changes only the routing decision.
- BootstrapFewShot is expected to be sufficient for this 4-5-way classification because the pinned Qwen3 model already understands paraphrase; if it is not, the run stops and reports rather than violating the AGENTS.md optimizer prohibition.
- The exact routing-accuracy and false-routing thresholds are plan-phase values set after a noise calibration run (feature 004 discipline: measure noise before setting gates).
- Reranking with the main LLM, multi-vector retrieval, UI changes, and any change to the structured query planning are explicitly out of scope for this feature.
