# Runner Report: Feature 009 — Synthetic Ticket Texts

**Status**: AUTOMATABLE WORK COMPLETE (T001-T013) — STOPPED AT MANUAL GATE T014
**Date**: 2026-10-13
**Executor**: Prime Agent (autonomous spec runner)

## Pre-implementation baseline (T001)

- Git commit at start: `fae42ae5f22f3a42c3599e3e87bb05401a2fb5c8` (branch `main`)
- Working-tree state at start: clean except untracked `specs/009-synthetic-ticket-texts/`.
- Baseline test result: `pytest -q` -> **417 passed, 0 failed** (115.99s), matching the
  expected pre-feature baseline. (The baseline run refreshes
  `artifacts/import-manifest.json`'s `import.imported_at` — known pre-existing
  fixture behavior, committed in 2dba29c.)
- Interpreter: `/usr/bin/python3` (Python 3.14.4)
- Stack: PostgreSQL 16.10-alpine + GraphJin 3.21.6 via `sudo -n docker compose`.

## Completed task IDs

T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011, T012, T013.

## Blocked / not-started task IDs

- **T014 (MANUAL GATE)**: NOT ticked — human data-quality review required (see below).
- T015-T024 (US2 import, US3 exposure, polish): NOT STARTED — hard-blocked on T014
  per the approved dependency graph (US2 consumes the approved artifact + the gate).

## Files changed

New:
- `app/ai/text_generation.py` (typed DSPy program, PROMPT_VERSION="1")
- `scripts/generate_ticket_texts.py`, `scripts/validate_ticket_texts.py`
- `data/raw/tickets_texts.jsonl` (2057-line pinned artifact, committed)
- `data/raw/texts-manifest.json` (provenance manifest, committed)
- `artifacts/llm-preflight-009.json`
- `tests/unit/test_text_generation_program.py` (14 tests)
- `tests/unit/test_ticket_texts_validation.py` (45 tests)
- `tests/unit/test_ticket_texts_checkpoint.py` (10 tests)
- `specs/009-synthetic-ticket-texts/runner-report.md` + approved design artifacts

Modified:
- `.gitignore` (transient checkpoint rule)
- `artifacts/import-manifest.json` (imported_at refresh from baseline fixture only)

Untouched (per scope): `evaluation/`, pinned `data/raw/*.csv`, `database/schema.sql`,
`graphjin/config/policies.yml`, `scripts/import_dataset.py` (US2 files — gated).

## Commits created (on `main`, not pushed)

```
ecd0189 feat(009): T012-T013 full generation + validation PASSED
340e8b9 docs(009): record deterministic batch failure + batch-size-4 regeneration decision
2330edf docs(009): park for the night - v2 regeneration checkpointed at 55 entries
aa9f499 fix(009): T013 source fixes after first validation failure
c6c415b feat(009): T010-T011 live sample + resume verification
9e94fa7 feat(009): T007-T009 generation program, validation suite, generator CLI
8b8c43f docs(009): approved design artifacts
3febfbb test(009): T004-T006 failing unit tests
2dba29c feat(009): T001-T003 baseline, LLM preflight, checkpoint gitignore
```

## Exact pinned versions

- Python 3.14.4 (`/usr/bin/python3`)
- dspy 3.4.0 (lm15 engine), pydantic 2.12.5, httpx 0.28.1, psycopg 3.3.6, pytest 9.0.3
- PostgreSQL 16.10-alpine, GraphJin 3.21.6 (pinned images)
- Exact API model ID: `models\Qwen3.8-27B-UD-Q4_K_M.gguf` (verified via GET /v1/models)
- llama.cpp version: **unreported** (endpoint exposes no build version via
  /v1/models, /props, or /health — checked 2026-10-12)
- No new dependencies installed.

## Validation commands and exact results

| Command | Result |
|---|---|
| `pytest -q` (baseline, T001) | **417 passed, 0 failed** |
| `pytest tests/unit/ -q` (final) | **153 passed, 0 failed** (84 pre-existing + 69 new) |
| `python scripts/validate_ticket_texts.py` (T013) | **exit 0 — VALIDATION PASSED: all 7 checks, 2057 entries** |
| `python scripts/generate_ticket_texts.py --sample 10` (T010) | exit 0, 2 batches, 0 violations |
| `python scripts/generate_ticket_texts.py --sample 25` + kill + resume (T011) | exit 0, resume from checkpoint, 25/25 unique, 0 violations |
| `python scripts/generate_ticket_texts.py --fresh --batch-size 4` (T012, v3) | exit 0, 515 batches, 2057/2057 |

T013 validation detail (all 7 checks pass on 2057/2057): schema+coverage
(every ticket exactly once), non-empty (no empty/slot-marker fields), lengths
(short_description 1 sentence <=100, description 2-4 sentences <=600,
resolution_notes 1-3 sentences <=450), english-only, secrets-pii-scan (zero
credential/PII patterns), category-consistency (20-pair lexicon), null-rule
(resolution_notes NULL exactly for the 250 open tickets, present for 1807 closed).
Result recorded in `data/raw/texts-manifest.json.validation`; artifact SHA-256
`72c96e92...f0ed` verified against the manifest.

## Live-generation summary (observational)

- **v1 full run** (batch-size 5): SIGTERM'd externally at 835/2057 (~55 min);
  resumed, completed 412/412, but T013 found 128 violations -> fixed AT SOURCE
  (commit aa9f499) and regenerated.
- **v2 full run** (batch-size 5, --fresh): parked overnight at 55/2057 (human
  decision); resumed, reached 1830/2057, then batch [849031..849035] failed
  DETERMINISTICALLY (model duplicates 849033, drops 849035, a 2FA Reset ticket,
  in an all-open composition at temperature 0). Discarded (pre-approval).
- **v3 full run** (batch-size 4, --fresh): reached 1848/2057, batch
  [849049..849052] failed (5 entries for a 4-ticket all-open batch, one id
  duplicated); did NOT reproduce on resume. Completed 515/515, 2057/2057.
- Batch config actually used (recorded in manifest): batch_size 4, max_retries 2,
  batches 515, retries_used 0 (final v3 segments).
- Runtime (observational only): v3 first segment ~4943s (1848 tickets) + resume
  segment ~402s (209 tickets) ~= 89 min total generation wall time.
- Seed 20261012, temperature 0, cache false, prompt_version "1".

### Known failure mode (recorded per launcher note)

The deterministic batch failures are an **all-open-composition family**: when
every ticket in a batch is open (all resolution_notes must be null), the model
occasionally confuses ticket_ids across the similar open tickets (duplicating
one id, dropping another). Observed at batch-size 5 ([849031..849035],
deterministic) and batch-size 4 ([849049..849052], did not reproduce on resume).
Mitigation used: batch-size tuning within the spec's approved 'about 5' range +
checkpoint/resume. The per-batch zero-tolerance acceptance caught every case;
no invalid entry ever reached the artifact.

## Security-effect and disclosure results

US1 (generation) never touches the database — the generator writes only files.
The secrets/PII scan (check 5) found zero credential-like or personal-data
patterns across all 2057 entries. No endpoint details, credentials, or prompts
were written to committed files or user-facing output (the manifest records
only the model ID, non-secret versions, seed, and hashes). US2/US3 security
re-verification (read-only enforcement, write rejection) is gated behind T014.

## Known limitations

- llama.cpp build version is unreported by the endpoint (recorded as such).
- Byte-identical cross-environment regeneration is NOT claimed (spec
  Assumptions): governance = strict per-entry validation + deterministic suite
  + artifact pinning with checksums + full-version regeneration only.
- The all-open-composition failure mode (above) may recur on regeneration;
  batch-size 4 + resume mitigated it this run.
- Category-consistency is a deterministic lexicon check (mechanical topic
  consistency), not literary quality judgment — deep review is the human gate.

## MANUAL GATE (T014) — exact human decision required

The artifact `data/raw/tickets_texts.jsonl` (2057 entries) passed the full
deterministic validation suite (exit 0) and is committed with its provenance
manifest. **The human must now perform the data-quality review** (quickstart
step 5): review per-category samples covering **all 5 categories** (e.g. ~5
tickets each, including open AND closed tickets) and judge text quality
(realism, coherence, category fit, priority-appropriate tone).

If satisfied, the HUMAN (never an agent) sets in `data/raw/texts-manifest.json`:
```json
"human_review": {"approved": true, "reviewer": "<name>",
  "reviewed_at": "<ISO-8601>", "sample_notes": "<notes>"}
```
and ticks `- [ ] T014` in `specs/009-synthetic-ticket-texts/tasks.md`.

Only after that may US2 (T015-T018: schema columns + atomic import) and US3
(T019-T021: GraphJin read-only exposure) begin — the import script enforces
`human_review.approved == true` and refuses otherwise.

## Launcher notification

Attempted 2026-10-13 after T013 passed: `agent_observe.list_agents()` does NOT
list `spec009-launcher-2026-10-12` as an active sibling, and
`agent_message.send(..., receiver_name='spec009-launcher-2026-10-12')` failed
with `RuntimeError: No sibling matches "spec009-launcher-2026-10-12"`.
**Delivery failed** — the named launcher sibling is absent/inactive. This
report file is retained as the complete record; the human can read the MANUAL
GATE instructions directly from the section above.
