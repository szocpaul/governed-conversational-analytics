# Research: Query Discovery UI

**Date**: 2026-10-12 | **Feature**: specs/008-query-discovery-ui

No NEEDS CLARIFICATION items remained after specification; this file records
the design decisions and the alternatives considered.

## Decision 1: Curated example list as a static JSON asset

- **Decision**: Store the example gallery content in a new static file
  `app/web/examples.json`, served by the existing FastAPI `StaticFiles`
  mount at `/static/examples.json`, and fetched once by `app.js` on page
  load.
- **Rationale**: FR-008 forbids new runtime data dependencies. A static
  asset is version-controlled (curation is reviewable in Git diffs),
  requires zero backend code, and degrades gracefully (if the fetch fails,
  the page still accepts free text — spec edge case).
- **Alternatives considered**:
  - *New `/api/examples` endpoint*: unnecessary backend surface for static
    content; rejected.
  - *Inline the questions in `index.html`*: harder to validate
    programmatically (the curation test would parse HTML); mixes content
    with markup; rejected.
  - *Derive from `evaluation/*.json` at runtime*: couples the UI to the
    evaluation corpus, violating dataset-isolation discipline (AGENTS.md);
    rejected. The curated list may quote validated questions but is a
    separate file.

## Decision 2: No frontend framework

- **Decision**: Plain JavaScript, same style as the existing `app.js`
  (ES5-compatible IIFE, no build step).
- **Rationale**: The existing file is ~80 lines and framework-free; adding a
  framework/build toolchain for a dropdown and a collapsible panel would be
  unjustified complexity. Consistency with spec 004 conventions.
- **Alternatives considered**: React/HTMX — rejected (new dependency chain,
  build step, no payoff at this scale).

## Decision 3: Interaction model — gallery click-to-submit, suggestions fill-only

- **Decision**: Clicking a gallery example fills the input AND submits it
  (identical to the existing `.example` button behavior). Selecting a typing
  suggestion only fills the input; the user submits with Enter/Ask.
- **Rationale**: The current four example buttons already auto-submit and
  users know that pattern; keeping it avoids inventing a second behavior for
  the same gesture. Suggestions appear mid-typing, where auto-submit would
  be surprising; fill-only is the standard autocomplete contract. Both
  satisfy FR-002.
- **Alternatives considered**: fill-then-submit everywhere — rejected for
  the gallery (breaks the established one-click demo flow).

## Decision 4: Suggestion matching rules

- **Decision**: Case-insensitive substring match over the curated list;
  minimum 3 typed characters; maximum 5 suggestions; first-match ordering by
  category order then list order. Keyboard: ArrowDown/ArrowUp to move, Enter
  to select, Escape to close. Placeholder rotation every 4 seconds while the
  input is empty and not being edited.
- **Rationale**: Simple, deterministic, testable; no scoring/fuzzy logic
  needed over a <100-entry list.
- **Alternatives considered**: fuzzy matching / ranking — rejected
  (over-engineering for this list size).

## Decision 5: Verifying "every gallery question is answerable" (SC-002)

- **Decision**: New script `evaluation/verify_examples.py`
  (`python -m evaluation.verify_examples --output artifacts/examples-verification.json`)
  that loads `examples.json`, posts each `answerable` question to the live
  pipeline (same path as `evaluation/run.py`), and asserts a grounded,
  non-clarification answer. Questions flagged as intentional refusals are
  asserted to be refused. The script is read-only and writes a versioned
  artifact with per-question outcomes.
- **Rationale**: SC-002 demands an end-to-end measurement, not a unit mock.
  Reusing the evaluation module pattern keeps conventions; the script never
  touches evaluation case files and never writes to the database.
- **Alternatives considered**:
  - *Extend `evaluation/run.py`*: rejected — that harness is pinned to the
    held-out corpus and baseline discipline; mixing UI content checks into
    it would blur responsibilities.
  - *Live pytest test in `pytest -q`*: rejected for the default gate —
    `pytest -q` must stay runnable without live services; the live check is
    a separate documented command (quickstart.md), consistent with how
    evaluation runs are separate commands in this project.

## Decision 6: Static overview content, hand-curated

- **Decision**: The dataset overview (3 subjects + dimensions) is curated
  text embedded in `index.html` (and mirrored into `examples.json` metadata
  only if needed by tests), NOT generated from GraphJin introspection.
- **Rationale**: The governed schema is small and stable; introspection adds
  runtime coupling and leak surface for zero practical benefit. FR-005 (no
  over-promising) is enforced by the curation unit test cross-checking the
  advertised dimension list against an allowlist derived from the governed
  model documentation.
- **Alternatives considered**: GraphJin introspection endpoint — rejected
  (runtime coupling, security surface).
