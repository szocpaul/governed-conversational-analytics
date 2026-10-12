# Quickstart: Query Discovery UI validation

**Date**: 2026-10-12 | **Feature**: specs/008-query-discovery-ui

## Prerequisites

- Repository checkout with the feature implemented.
- For the automated gate: only Python dev dependencies (`pytest`).
- For live verification (SC-002): PostgreSQL + GraphJin running per
  `compose.yml`, and the configured local llama.cpp endpoint reachable
  (same prerequisites as `python -m evaluation.run`).

## 1. Automated gate (no live services)

```bash
pytest -q
```

Expected: all tests pass, including:

- `tests/unit/test_examples_curation.py` — examples.json structure,
  category/count rules, corpus alignment, no prohibited strings.
- `tests/integration/test_demo_interface.py` — overview card, gallery
  markup, suggestions container present; examples.json served; no private
  endpoint/canary strings in any served asset; existing query-flow tests
  unchanged and green.

## 2. Live gallery verification (SC-002)

```bash
python -m evaluation.verify_examples --output artifacts/examples-verification.json
```

Expected: exit code 0; the artifact reports every `answerable` gallery
question with a grounded answer (status `answered`) and every
`refusal_demo` question refused. Any clarification/error on an answerable
question exits non-zero.

## 3. Manual smoke (human, at the MANUAL GATE)

1. Start the app: `uvicorn app.main:app --host 127.0.0.1 --port 8001`.
2. Open `http://127.0.0.1:8001/`.
3. Read the overview card: confirm tickets, merchants, agents and at least
   5 dimensions are described in plain language (SC-004).
4. Open the gallery, click any example: answer + trace + latency appear
   (SC-001, zero typing).
5. Watch the placeholder rotate while the input is empty; type "How many
   tickets" and confirm suggestions appear, Enter fills the input, Escape
   closes the box.
