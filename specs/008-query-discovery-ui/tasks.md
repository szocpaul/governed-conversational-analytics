# Tasks: Query Discovery UI

**Input**: Design documents from `/specs/008-query-discovery-ui/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — AGENTS.md requires tests before implementation, with
the expected failure observed first.

**Organization**: Tasks are grouped by user story (US1 gallery = P1, US2
overview = P2, US3 input guidance = P3) so each story is independently
implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 — maps to spec.md user stories
- All file paths are repository-relative

## Phase 1: Setup

- [X] T001 Create the curated example list `app/web/examples.json`: at least 15 questions across at least 4 categories per `specs/008-query-discovery-ui/data-model.md` (`categories` array + `examples` array with `question`, `category`, `outcome` fields; exactly one `refusal_demo` entry with a `note`, reusing the existing injection demo question). Source `answerable` questions from the validated corpus (`evaluation/dev_cases.json`, `evaluation/cases.json`) by normalized text; add GROUP BY/ratio examples validated by feature 005. Do NOT modify any file under `evaluation/`.

## Phase 2: Foundational (tests first — BLOCKS all user stories)

- [X] T002 Write `tests/unit/test_examples_curation.py` enforcing the data-model rules: schema shape, >=15 entries, >=4 categories, categories match declared list, `outcome` in {answerable, refusal_demo}, every answerable question present in the evaluation corpus by normalized text OR explicitly allowlisted in the test, refusal demos carry a `note`, no prohibited strings (private endpoint host `tailee6bc1`, port `8033`, `CANARY`, credential-like patterns). Run `pytest tests/unit/test_examples_curation.py -q` and observe FAIL (file under test missing).
- [X] T003 Extend `tests/integration/test_demo_interface.py` with tests for the new DOM contract (`specs/008-query-discovery-ui/contracts/ui-contract.md`): GET `/static/examples.json` returns 200 JSON; served HTML contains `#dataset-overview` naming tickets/merchants/agents, `#gallery-toggle`, `#gallery`, `#suggestions`; no-leak assertions extended to `/static/examples.json`. Run and observe FAIL.

## Phase 3: User Story 1 — Browsable example-question gallery (P1)

**Goal**: A newcomer can open a categorized gallery of known-good questions
and run any of them with one click.

**Independent Test**: Open `/`, expand the gallery, click any example,
receive a grounded answer with trace and latency — zero typing.

- [X] T004 [US1] Iterate on `app/web/examples.json` until `pytest tests/unit/test_examples_curation.py -q` passes (fix content, never weaken the test).
- [X] T005 [US1] Update `app/web/index.html`: replace the four fixed `.example` buttons with a collapsible gallery panel (`#gallery-toggle` button, `#gallery` panel) rendered by JS; keep the labeled security/refusal demo as a gallery category; keep `action`-relevant existing IDs (`ask-form`, `question`, `ask-btn`, result section) unchanged.
- [X] T006 [US1] Update `app/web/app.js`: fetch `/static/examples.json` once on load; render one `.gallery-category` section per category with `.gallery-example` buttons (`data-q` = full question); click fills `#question` and submits the form (existing pattern); on fetch failure hide the gallery and leave free-text flow fully working (graceful degradation); remove the hard-coded `.example` wiring.
- [X] T007 [US1] Update `app/web/styles.css`: styles for `#gallery-toggle`, `#gallery`, `.gallery-category`, `.gallery-example`, consistent with the existing visual language.
- [X] T008 [US1] Create `evaluation/verify_examples.py` (runnable as `python -m evaluation.verify_examples --output artifacts/examples-verification.json`): load `app/web/examples.json`, run every `answerable` question through the live pipeline (same code path as `evaluation/run.py`), require a grounded non-clarification answer; require every `refusal_demo` question to be refused; write per-question outcomes + metadata (versions, timestamp, artifact hash) to the output file; exit non-zero on any failure. Read-only: no DB writes, no evaluation-corpus changes. Execute it live and record the result.
- [X] T009 [US1] Run `pytest -q` and confirm the whole suite is green (including T002/T003 tests and all pre-existing tests — no regressions, FR-010).

## Phase 4: User Story 2 — Plain-language dataset overview (P2)

**Goal**: A newcomer sees what data exists and what dimensions are askable,
without external documentation.

**Independent Test**: Open `/`, read `#dataset-overview`: three subjects and
>=5 dimensions in business terms.

- [X] T010 [US2] Update `app/web/index.html`: add the `#dataset-overview` card next to the ask section — one plain-language sentence each for tickets, merchants, agents, plus a dimension list of at least 5 business-term labels (e.g. priority, category, SLA compliance, CSAT score, resolution time, status, reopen count, merchant, assigned agent). Every advertised dimension must be answerable by the governed query layer (FR-005).
- [X] T011 [US2] Extend `tests/unit/test_examples_curation.py` with a dimension allowlist cross-check (advertised dimensions in `index.html` vs. an allowlist in the test derived from the governed model) and update `app/web/styles.css` for the overview card. Run `pytest -q`, confirm green.

## Phase 5: User Story 3 — Guided query input (P3)

**Goal**: The input itself teaches: rotating placeholder examples plus
typing suggestions from the curated list.

**Independent Test**: Empty input shows a placeholder that rotates every 4s;
typing "How many tickets" shows up to 5 suggestions; Enter fills, Escape
closes, free-text submission unaffected.

- [X] T012 [US3] Update `app/web/app.js`: placeholder rotation through at least 3 curated questions every 4 seconds while the input is empty and untouched; stop rotating permanently once the user types.
- [X] T013 [US3] Update `app/web/app.js`: suggestion dropdown in `#suggestions` — case-insensitive substring match over the curated list, minimum 3 typed characters, maximum 5 items; click or Enter fills `#question` (no auto-submit); Escape closes; hidden when no match; normal typing/submission never blocked. Update `app/web/index.html` with the `#suggestions` container.
- [X] T014 [US3] Update `app/web/styles.css`: suggestion dropdown styles (positioning, highlight, keyboard-selected state).

## Phase 6: Polish & Validation

- [X] T015 Run the full validation gate set from `specs/008-query-discovery-ui/quickstart.md`: `pytest -q` green; `python -m evaluation.verify_examples --output artifacts/examples-verification.json` exit 0 with the artifact committed. Fix any failure at its source.
- [X] T016 Write `specs/008-query-discovery-ui/runner-report.md`: completed task IDs, files changed, commits, validation commands and exact results, live verification summary (per-category counts, refusals), known limitations, outstanding manual gate. Send a concise status summary to the launcher sibling session if one is reachable (verify the exact sibling name first; otherwise record the delivery failure in the report).
- [ ] T017 MANUAL GATE — Human UI review: open the demo page, walk quickstart.md section 3 (manual smoke), confirm SC-001..SC-005, then tick this box. DO NOT let an automated agent tick, approve, or bypass this gate.

## Dependencies

```text
T001 -> T002 -> T004          (curation content -> test -> green)
T003 (markup contract tests) blocks T005/T010/T013 implementation validation
US1 (T004-T009) -> US2 (T010-T011) -> US3 (T012-T014)   [priority order]
T015 depends on all stories; T016 on T015; T017 is the final MANUAL GATE
```

User stories are independently deliverable: US1 alone is a viable MVP;
US2 and US3 each add value without rework of earlier stories.

## Parallel Execution Examples

- T002 and T003 can be written in parallel (different test files).
- Within US1: T005 (HTML), T006 (JS), T007 (CSS) touch different files and
  can be drafted in parallel, then integrated.
- T012 and T014 touch different files (JS vs CSS) and can run in parallel.

## Implementation Strategy

1. Setup + Foundational: curate content, write failing tests (T001-T003).
2. MVP = Phase 3 (US1): the gallery alone delivers the core value; stop
   here only if time-boxed.
3. Increment: US2, then US3.
4. Polish: gates + report, then STOP at the MANUAL GATE (T017).
