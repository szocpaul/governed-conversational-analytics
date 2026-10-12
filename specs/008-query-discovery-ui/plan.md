# Implementation Plan: Query Discovery UI

**Branch**: `008-query-discovery-ui` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-query-discovery-ui/spec.md`

## Summary

Make the demo web interface self-explanatory for users who do not know the
ITSM dataset. Three capabilities, all frontend-only on the existing demo UI
(`app/web/`): (1) a categorized gallery of curated, verified-answerable
example questions; (2) a plain-language dataset overview (tickets, merchants,
agents + askable dimensions); (3) guided input via rotating placeholder
examples and typing suggestions. All content comes from a new curated,
version-controlled static asset (`app/web/examples.json`) — no new runtime
data dependencies, no backend API change, no model calls. A live verification
script proves every answerable gallery question returns a grounded answer
(SC-002).

## Technical Context

**Language/Version**: Python 3.14.4 (backend/tests); vanilla ES5-style
JavaScript, HTML, CSS (frontend, consistent with existing `app/web/`, no
framework, no build step)

**Primary Dependencies**: FastAPI + StaticFiles (already serving `app/web/`);
pytest + fastapi.testclient for tests; no new dependencies

**Storage**: N/A (curated example list is a static JSON asset in Git)

**Testing**: pytest (`pytest -q`), plus a live verification script
`python -m evaluation.verify_examples` for SC-002

**Target Platform**: Demo web UI served by the FastAPI app at `/` with assets
under `/static/` (current deployment: uvicorn, documented default
127.0.0.1:8001)

**Project Type**: web-service (frontend surface of an existing governed
analytics backend)

**Performance Goals**: N/A (static assets; suggestions computed client-side
over a <100-entry list; latency gates are prohibited as pass/fail criteria
per AGENTS.md)

**Constraints**: No backend API change (additive read-only only if truly
needed); no new runtime data dependencies or external calls (FR-008); no
exposure of prompts, private endpoint, credentials (FR-009); evaluation
corpus files (`evaluation/dev_cases.json`, `evaluation/cases.json`) MUST NOT
be modified or coupled to the UI; UI language English (FR-011)

**Scale/Scope**: 1 HTML page, 1 JS file, 1 CSS file, 1 new JSON asset
(~15-25 curated questions), 2 test modules, 1 verification script

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`.specify/memory/constitution.md`) is an
unfilled template; the effective governance document is `AGENTS.md`.

| AGENTS.md rule | Check |
|---|---|
| No arbitrary SQL / GraphJin bypass | PASS — feature is frontend-only; query path untouched |
| No credentials / private endpoint in UI or traces | PASS by design (FR-009); covered by extending `test_ui_does_not_embed_private_endpoint`-style checks to new assets |
| No real/personal data | PASS — examples reference only the approved synthetic ITSM dataset |
| Evaluation corpus isolation | PASS — `evaluation/*.json` untouched; curated list is a separate artifact that may *quote* validated questions |
| No latency as pass/fail gate | PASS — no performance gates in this feature |
| MANUAL GATE discipline | PASS — tasks.md ends with a MANUAL GATE for human UI review |

Post-design re-check: PASS (see Phase 1 artifacts; no violations).

## Project Structure

### Documentation (this feature)

```text
specs/008-query-discovery-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (ui-contract.md)
└── tasks.md             # /speckit-tasks output
```

### Source Code (repository root)

```text
app/web/
├── index.html           # MODIFIED: gallery panel, overview card, suggestion container
├── app.js               # MODIFIED: gallery render, click-to-submit, placeholder
│                        #   rotation, suggestion dropdown
├── styles.css           # MODIFIED: styles for gallery, overview, suggestions
└── examples.json        # NEW: curated categorized example list (static asset)

evaluation/
└── verify_examples.py   # NEW: live end-to-end verification of gallery questions
                         #   (SC-002), additive read-only, follows evaluation/run.py
                         #   conventions; writes artifacts/examples-verification.json

tests/
├── unit/
│   └── test_examples_curation.py   # NEW: examples.json structure/content rules
└── integration/
    └── test_demo_interface.py      # MODIFIED: gallery/overview/suggestions markup,
                                    #   examples.json served, no-leak checks extended
```

**Structure Decision**: Frontend-only extension of the existing demo UI
(`app/web/`, served via FastAPI StaticFiles). The only backend-adjacent
addition is a read-only verification script under `evaluation/`. No new
packages, no API routes, no database or GraphJin changes.

## Complexity Tracking

No constitution violations; nothing to justify.
