# Data Model: Query Discovery UI

**Date**: 2026-10-12 | **Feature**: specs/008-query-discovery-ui

No database changes. The only data artifact is the curated static asset
`app/web/examples.json`.

## Entity: Example Question

One entry in the curated gallery.

| Field | Type | Required | Rules |
|---|---|---|---|
| `question` | string | yes | Non-empty English question; unique across the list |
| `category` | string | yes | Must be one of the categories declared in `categories` |
| `outcome` | string | yes | `"answerable"` or `"refusal_demo"`; no other values |
| `note` | string | no | Short UI hint, e.g. why the refusal demo is refused |

Validation rules (enforced by `tests/unit/test_examples_curation.py`):

- At least 15 entries total and at least 4 distinct categories (FR-001).
- Exactly the categories listed in `categories` are used by entries.
- Every `answerable` entry MUST appear in the validated evaluation corpus
  (`evaluation/dev_cases.json` or `evaluation/cases.json`, matched by
  normalized question text) OR be explicitly allowlisted in the test as
  manually verified (FR-003). Refusal demos are exempt.
- At most a small fixed number of `refusal_demo` entries (recommend 1),
  each carrying a `note` (edge case: clearly labeled).
- No entry may contain the private endpoint host/port, canary markers, or
  credential-like strings (FR-009).

## Entity: Gallery (file root)

```json
{
  "categories": ["Counts & totals", "Priority & category",
                 "SLA & quality", "Aggregations & comparisons",
                 "Security demo"],
  "examples": [ { "question": "...", "category": "...", "outcome": "answerable" } ]
}
```

## Entity: Dataset Overview Entry (curated text, embedded in index.html)

| Field | Type | Rules |
|---|---|---|
| `subject` | string | One of: tickets, merchants, agents |
| `description` | string | One plain-language sentence |
| `dimensions` | list[string] | Business-term labels (e.g. "priority", "CSAT score", "resolution time", "SLA compliance"); each MUST map to a capability of the governed query layer (FR-005), cross-checked against an allowlist in the curation test |

## State Transitions

N/A — static content. The only runtime state is client-side UI state
(gallery open/closed, suggestion index, placeholder rotation timer), which
is ephemeral and not persisted.
