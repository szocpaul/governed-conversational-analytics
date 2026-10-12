# Runner Report: Feature 008 — Query Discovery UI

**Date**: 2026-10-12
**Runner session**: spec008-runner-2026-10-12
**Status**: T001–T016 COMPLETE. T017 (MANUAL GATE) pending human review.

## 1. Completed task IDs

T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011, T012,
T013, T014, T015, T016 (this report).

## 2. Incomplete or blocked task IDs

None. T017 (MANUAL GATE — human UI review) intentionally left unchecked.

## 3. Files changed

| File | Change |
|---|---|
| `app/web/examples.json` | NEW — curated gallery: 21 questions, 5 categories (20 answerable, all verbatim from the validated evaluation corpus; 1 labeled refusal demo) |
| `app/web/index.html` | MODIFIED — replaced 4 hard-coded `.example` buttons with `#gallery-toggle` + `#gallery` (JS-rendered), added `#dataset-overview` card (3 subjects, 12 `data-dimension` labels), added `#suggestions` container; existing IDs (`ask-form`, `question`, `ask-btn`, result section) unchanged |
| `app/web/app.js` | MODIFIED — fetch `/static/examples.json` once on load; gallery render + click-to-submit; graceful degradation on fetch failure; placeholder rotation (4s, >=3 curated questions, stops permanently on first input); suggestion dropdown (substring match, min 3 chars, max 5, click/Enter fill-only, Escape closes, arrows navigate); hard-coded `.example` wiring removed |
| `app/web/styles.css` | MODIFIED — gallery, overview card, and suggestion styles; removed unused `.examples`/`.example` rules |
| `tests/unit/test_examples_curation.py` | NEW — 10 curation tests (schema, counts, category discipline, outcome values, uniqueness, exactly-one refusal demo with note, corpus-backing of answerable questions, prohibited strings, FR-005 dimension allowlist) |
| `tests/integration/test_demo_interface.py` | EXTENDED — 4 new tests (examples.json served, overview names all subjects, gallery/suggestions DOM hooks, no-leak assertions extended to examples.json) |
| `evaluation/verify_examples.py` | NEW — live end-to-end gallery verification (SC-002), `python -m evaluation.verify_examples --output ...`, read-only, exits non-zero on failure |
| `artifacts/examples-verification.json` | NEW — versioned verification artifact (pinned metadata, per-question outcomes) |
| `specs/008-query-discovery-ui/*` | NEW — spec artifacts + this report |

NOT touched (per scope): `evaluation/dev_cases.json`, `evaluation/cases.json`,
`evaluation/security_cases.json`, `evaluation/run.py`, all pipeline/security
code. The pre-existing uncommitted modification of
`artifacts/import-manifest.json` (present before this feature started) was
left untouched and uncommitted.

## 4. Commits

- One commit on `main`: "Feature 008: Query Discovery UI (T001-T016)"
  (HEAD at report time), containing all files listed in section 3. The
  unrelated pre-existing modification of `artifacts/import-manifest.json`
  was deliberately excluded.

## 5. Validation commands and exact results

- Baseline before feature: `pytest -q` → **403 passed** (82s).
- TDD red state (T002/T003, file/markup missing):
  `pytest tests/unit/test_examples_curation.py tests/integration/test_demo_interface.py -q`
  → **13 failed, 6 passed** (expected failures observed before implementation).
- After implementation:
  `pytest tests/unit/test_examples_curation.py tests/integration/test_demo_interface.py -q`
  → **19 passed**.
- Full gate (T009/T015): `pytest -q` → **417 passed** (95s). Zero regressions.
- Live verification (T008/T015):
  `python -m evaluation.verify_examples --output artifacts/examples-verification.json`
  → **exit 0**, `all_passed: true`.
- `node --check app/web/app.js` → OK.

## 6. Live verification summary (SC-002)

21/21 questions passed against the live pipeline
(LLM Qwen3 27B via llama.cpp, temperature 0, cache disabled;
DSPy 3.4.0; code a9f3381 + this feature):

| Category | Total | Passed |
|---|---|---|
| Counts & totals | 4 | 4 |
| Priority & category | 4 | 4 |
| SLA & quality | 5 | 5 |
| Aggregations & comparisons | 7 | 7 |
| Security demo | 1 | 1 |

- 20/20 answerable questions → status `answered` with evidence (grounded).
- 1/1 refusal demo → status `unsupported`, `refused` trace event, no query
  executed.
- 0 clarifications, 0 disclosures (no endpoint/canary strings in any
  response).

Note: a first verification run reported one clarification on
"Which merchants have more than 25 tickets?" while `pytest -q` was running
concurrently against the same single-slot LLM server. A clean rerun without
concurrent load passed 21/21, and a manual re-query of the same question
returned a grounded answer; the flake is attributed to load contention, not
to gallery wording (the question is verbatim DEV-016 from the validated
corpus).

## 7. Security-effect and disclosure results

- No-leak tests extended to `/static/examples.json`: no private endpoint
  host/port, no canary markers, no credential-like patterns in any served
  asset (unit + integration tests, green).
- Live verification: `disclosures: 0` across all 21 questions; refusal demo
  produced no executed query.
- `artifacts/examples-verification.json` contains pinned metadata only
  (model artifact name, versions, hashes); no endpoint URL.

## 8. Latency (observational only)

Live verification run (21 questions): median **3040 ms**,
p90 **3492 ms**, max **5059 ms**, min 1103 ms. Observational only; not a
pass/fail gate per AGENTS.md.

## 9. Known limitations

- Gallery/suggestion behavior is client-side JS; automated tests cover the
  DOM contract and served assets, not browser interaction (browser smoke is
  the T017 manual gate).
- The placeholder rotation and suggestions depend on
  `/static/examples.json`; if the fetch fails the page degrades to the
  pre-008 free-text flow (by design, tested via code path, not browser).
- Suggestion ordering is category order then list order (no fuzzy ranking),
  per research.md Decision 4.

## 10. Outstanding manual gates

- **T017 MANUAL GATE** — Human UI review per quickstart.md section 3
  (overview readability SC-004, gallery one-click run SC-001, placeholder
  rotation + suggestion interaction, SC-005 no-regression spot check).
  Unchecked; awaiting human approval.

## 11. Launcher notification

Status summary sent to sibling session `spec008-launcher-2026-10-12`
(verified via agent roster).

## 12. MANUAL GATE outcome (2026-10-12)

**T017 APPROVED by the human reviewer.** During review two UX issues were
found and fixed:

- Commit `091775c`: the result panel (status/answer/latency/trace) moved
  directly below the query input — previously it rendered at the bottom of
  the page and required scrolling after every question.
- Commit `54b0c6b`: spacing added between the result panel and the
  "Browse example questions" toggle (they visually collided).

The reviewer then re-tested all gallery buttons and interactions in the
browser and approved the gate. T017 is ticked in tasks.md.

**Feature 008 (Query Discovery UI) is COMPLETE: T001-T017 done.**
