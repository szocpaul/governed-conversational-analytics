# UI Contract: Query Discovery UI

**Date**: 2026-10-12 | **Feature**: specs/008-query-discovery-ui

No HTTP API changes. This contract fixes the DOM-level behaviors and the
static-asset schema that tests and the verification script rely on.

## Asset: GET /static/examples.json

Served by the existing StaticFiles mount (no code change needed once the
file exists in `app/web/`).

- Response: 200, `application/json`.
- Body schema: `{ "categories": [string, ...], "examples": [ExampleQuestion, ...] }`
  (see `data-model.md`).
- Availability: if this fetch fails, the page MUST still render and accept
  free-text questions (graceful degradation).

## DOM contract (hooks the implementation and tests agree on)

| Element | Selector | Behavior |
|---|---|---|
| Overview card | `#dataset-overview` | Always visible; names tickets, merchants, agents; lists >=5 dimensions |
| Gallery toggle | `#gallery-toggle` | Expands/collapses the gallery panel |
| Gallery panel | `#gallery` | Contains one `.gallery-category` section per category |
| Gallery example | `.gallery-example` | `data-q` holds full question text; click fills `#question` and submits the form |
| Suggestion box | `#suggestions` | Hidden unless >=3 chars typed and >=1 match; max 5 `.suggestion` items |
| Suggestion item | `.suggestion` | Click or Enter fills `#question` (no auto-submit); Escape closes box |
| Query input | `#question` | Placeholder rotates through >=3 curated questions every 4s while input is empty and untouched |

## Invariants (must hold after the feature)

- POST `/query` request/response shape is unchanged.
- `/`, `/static/app.js`, `/static/styles.css`, `/static/examples.json` never
  contain the private endpoint host or port, canary markers, or credentials.
- All new UI text is English.
