# Feature Specification: Query Discovery UI

**Feature Branch**: `008-query-discovery-ui`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Make the demo frontend usable for people who do not know the ITSM dataset, so they can start relevant queries: (1) a categorized gallery of validated example questions, (2) a plain-language overview of what data is available, (3) input guidance via rotating placeholder examples and typing suggestions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browsable example-question gallery (Priority: P1)

A visitor who has never seen the ITSM dataset opens the demo page. Instead of a blank input with four hard-coded buttons, they see an expandable, categorized gallery of example questions (e.g., counts, priority/category breakdowns, SLA and CSAT quality metrics, aggregations, and a clearly labeled security/refusal demo). They click a question that sounds interesting, the input is filled with it, and they can run it immediately.

**Why this priority**: This is the single biggest lever for a newcomer: it turns "what can I even ask?" into a menu of known-good choices. Every other improvement builds on this.

**Independent Test**: Load the demo page, open the gallery without typing anything, click any example, submit it, and receive a grounded answer. Delivers value even if Stories 2 and 3 are absent.

**Acceptance Scenarios**:

1. **Given** the demo page is open, **When** the user opens the example gallery, **Then** they see at least 15 example questions grouped into at least 4 meaningful categories.
2. **Given** the gallery is open, **When** the user clicks an example question, **Then** the full question text appears in the query input and the user can submit it without retyping.
3. **Given** any example question in the gallery, **When** it is submitted, **Then** the system returns a grounded answer or a documented, intentional refusal (the security demo example), never a clarification caused by gallery wording.
4. **Given** the gallery is open, **When** the user submits an example, **Then** the existing answer, trace, and latency display still works unchanged.

---

### User Story 2 - Plain-language dataset overview (Priority: P2)

A visitor wants to know what the dataset even contains before asking anything. Next to the query input they see a compact, plain-language summary of the three data subjects (tickets, merchants, agents) and the main dimensions they can ask about (e.g., priority, category, SLA, CSAT, resolution time, status), so they can form their own question beyond the examples.

**Why this priority**: The gallery gives ready-made questions; the overview lets users compose their own. It is the second-most important discovery aid, but the page is already useful with Story 1 alone.

**Independent Test**: Load the page, read the overview, and verify a newcomer can name the three data subjects and at least five askable dimensions without reading any external documentation.

**Acceptance Scenarios**:

1. **Given** the demo page is open, **When** the user views the overview area, **Then** all three data subjects (tickets, merchants, agents) are named with a one-line plain-language description each.
2. **Given** the overview area, **When** the user scans the dimension list, **Then** at least five query dimensions are listed in business terms (not raw column names).
3. **Given** the overview content, **When** compared against the governed data model, **Then** no dimension is advertised that the governed query layer cannot actually answer (no over-promising).

---

### User Story 3 - Guided query input (Priority: P3)

A visitor starts typing their own question. The input guides them in two passive ways: the placeholder cycles through several realistic example questions, and as they type, matching questions from the curated example list appear as selectable suggestions.

**Why this priority**: This helps users who bypass the gallery and go straight to typing. It reinforces discovery but is the least critical of the three; Stories 1 and 2 already make the page usable.

**Independent Test**: Load the page, observe the placeholder change across a defined rotation, type a partial phrase such as "How many tickets", and see at least one matching curated suggestion that fills the input when selected.

**Acceptance Scenarios**:

1. **Given** the demo page is open and the input is empty and untouched, **When** the rotation interval passes, **Then** the placeholder text cycles through at least 3 different curated example questions.
2. **Given** the user has typed at least a few characters, **When** the typed text prefix-matches or substring-matches curated examples, **Then** up to 5 matching suggestions are shown and selecting one fills the input.
3. **Given** the typed text matches nothing, **When** the user keeps typing, **Then** no suggestion box blocks or alters normal typing, and submission of free text still works exactly as before.

---

### Edge Cases

- If the curated example list is missing or empty, the page MUST still render and accept free-text questions (graceful degradation; gallery and suggestions simply do not appear).
- Gallery questions MUST be answerable by the governed pipeline: each published example is either covered by the validated evaluation corpus or manually verified, so users never hit clarification loops caused by the gallery itself.
- The labeled security/refusal example MUST remain clearly marked as a demonstration of a refused request, so users are not surprised by the refusal response.
- Suggestions MUST NOT fire on empty or near-empty input (e.g., fewer than 3 characters), to avoid noise.
- The feature MUST NOT reveal internal prompts, endpoint details, credentials, or raw schema names beyond the already-public governed data model descriptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The demo page MUST present a browsable gallery of at least 15 example questions, grouped into at least 4 categories meaningful to a non-technical user.
- **FR-002**: Selecting a gallery example MUST place its full text into the query input, allowing submission without retyping.
- **FR-003**: Every published example question MUST be verified answerable by the governed query pipeline (grounded answer or intentional, documented refusal); the gallery MUST NOT contain questions that produce wording-caused clarifications.
- **FR-004**: The demo page MUST display a plain-language overview naming all three data subjects (tickets, merchants, agents) and at least five askable dimensions in business terms.
- **FR-005**: The overview MUST NOT advertise dimensions or metrics that the governed query layer cannot answer.
- **FR-006**: The query input placeholder MUST rotate through at least 3 curated example questions while the input is empty and unfocused/unchanged.
- **FR-007**: While typing, the input MUST offer up to 5 matching suggestions drawn from the same curated example list, starting from a minimum of 3 typed characters.
- **FR-008**: All example/suggestion content MUST come from a curated, version-controlled list maintained in the repository; the feature MUST NOT introduce new runtime data dependencies, external calls, or model calls.
- **FR-009**: The feature MUST NOT expose internal prompts, private endpoint details, credentials, or any prohibited data in the UI, errors, or traces (consistent with the existing security posture).
- **FR-010**: The existing query flow (answer, status, latency, sanitized trace display, error handling) MUST continue to work unchanged for free-text questions.
- **FR-011**: The UI language of the new elements MUST be English, consistent with the existing demo interface.

### Key Entities *(include if feature involves data)*

- **Example Question**: A curated question string with a category label and an intentional-outcome flag (answerable vs. demonstration refusal). Source of truth is a version-controlled curated list, aligned with the validated evaluation corpus where applicable.
- **Dataset Overview Entry**: A plain-language description of a data subject (tickets, merchants, agents) or an askable dimension (e.g., priority, SLA, CSAT).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time visitor can find and run a relevant example question within 10 seconds of the page loading, with zero typing.
- **SC-002**: 100% of gallery examples marked answerable return a grounded answer when executed against the live system (measured by running every gallery question end-to-end).
- **SC-003**: The gallery offers at least 15 examples across at least 4 categories.
- **SC-004**: A visitor can identify all 3 data subjects and at least 5 askable dimensions from the page alone, without external documentation.
- **SC-005**: Zero regression in the existing free-text query flow: all pre-existing demo behaviors (including the refusal demo) pass their existing checks unchanged.

## Assumptions

- The UI remains English-only, matching the existing demo interface.
- The example list is curated and version-controlled in the repository (a new, small curated artifact), aligned with — but physically separate from — the evaluation corpus files (`evaluation/dev_cases.json`, `evaluation/cases.json`), which MUST NOT be modified or coupled to the UI.
- Click-to-submit behavior for examples matches the current demo (selecting an example may submit immediately or fill-then-submit; the plan decides, both satisfy FR-002).
- No personalization, query history, or per-user adaptation is in scope.
- No backend API change is expected; if the plan discovers one is needed, it must be additive and read-only.
- The feature targets the existing demo web interface only; no other clients exist.
