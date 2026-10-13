# Runner Report: Feature 009 — Synthetic Ticket Texts

**Status**: COMPLETE — all 24 tasks done (T014 MANUAL GATE approved by human); full gate 500/500 green
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

ALL: T001-T013 (US1), T014 (MANUAL GATE approved by human Pal Majoros 2026-10-13, commit c09cfdb), T015-T018 (US2), T019-T021 (US3), T022, T023, T024 (polish).

## Blocked / not-started task IDs

None. All 24 tasks complete.

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


## US2 (import) and US3 (exposure) completion — post-GATE

After the human approved T014 (commit c09cfdb):

- **T015**: `tests/integration/test_ticket_texts_import.py` written first, observed
  FAIL (7 failed, 1 trivially passing). Commit 0935e3e.
- **T016**: `database/schema.sql` — itsm.tickets gains short_description/description/
  resolution_notes (text, nullable, GENERATED comments) in CREATE TABLE + 3 idempotent
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Verified via initialize_database.py.
  Commit 56222d5.
- **T017**: `scripts/import_dataset.py` — loads the approved artifact inside the SAME
  single transaction: verifies artifact SHA-256 vs texts-manifest, coverage == pinned
  2057, NULL rule vs tickets.csv, and `human_review.approved == true` (all BEFORE any
  DB write; any failure = full rollback); UPDATEs the 3 generated columns per ticket;
  post-import count + NULL-rule checks in-transaction; additive `generated_texts` key
  in artifacts/import-manifest.json (existing keys untouched). TICKETS_TEXTS_PATH /
  TEXTS_MANIFEST_PATH env overrides = test seam for negative paths. Texts import is
  skipped when the artifact is absent (feature-001 fresh-checkout behavior intact).
  T015 8/8 pass; feature-001 import+init 16/16 green. Commit a0c46ad.
- **T018**: reset_database + initialize_database + import_dataset reproduces the full
  state (2057 tickets, 3 columns populated, NULL rule 250/1807); feature-001
  discipline 16/16 green. Commit 9a36ee1.
- **T019**: `tests/integration/test_graphjin_ticket_texts.py` — select of the 3 fields
  (100-row limit respected), is-null on resolution_notes (open tickets, DB cross-check
  = 250), combined priority+field filter, write attempts rejected with zero DB changes.
  6/6 pass. Commit 5d2a7f1.
- **T020**: `graphjin/config/policies.yml` tickets allowlist gains exactly the 3 columns
  (# GENERATED feature 009); no other config change (dev.yml untouched). GraphJin
  restarted; test_graphjin_queries 6/6 green. Commit 5d2a7f1.
  NOTE: GraphJin v3 with default_block + public_tables gates TABLES; the columns block
  is declarative — the new columns were already servable once imported. The explicit
  allowlist is now accurate; column-level read restriction is not enforced by this
  GraphJin version (recorded as a known limitation).
- **T021**: `pytest tests/security/ -q` = **94/94 pass** (read-only enforcement,
  authorization, limits/timeouts, redaction) with the 3 columns exposed. Commit a8971dd.

## T022 — full pytest gate: PASSED (500/500) after environmental fix

`pytest -q` = **499 passed, 1 failed**. The single failure is
`tests/integration/test_review_findings_live.py::test_f10_null_agent_filter_unsupported`,
which returns `dependency_error`: the answer-program request is 17361 tokens but the
LLM endpoint now reports **n_ctx = 8192** (verified via /props and /v1/models meta).

This is an ENVIRONMENT CHANGE, not a feature-009 regression:
- At the T001 baseline (2026-10-12 ~19:33) the endpoint reported **n_ctx = 65536**
  (verified via /props) and F10 passed (417/417).
- Feature 009 does NOT touch the query/answer path (query_program, answer_program,
  optimized_program, llm.py all unchanged); the F10 query selects only the 19 original
  fields (no generated text columns) with limit 100 — identical evidence size to baseline.
- The pipeline is otherwise healthy: "Show 5 tickets where assigned agent is missing"
  -> answered; "How many tickets have no assigned agent?" -> answered (250). Only the
  100-full-row F10 question overflows the reduced 8192 context.
- Root cause: the llama.cpp server was restarted with a smaller per-slot context
  (8192) after the baseline; the approved configuration uses a much larger context
  (the operator runs -c 262144).

Per the stop-and-report discipline I did NOT improvise a workaround (reducing the
limit or truncating evidence would mask an environment change by altering approved
behavior). **Human action needed**: restart the llama.cpp server with the approved
large context (e.g. -c 262144 / the prior 65536), then re-run `pytest -q` — F10
should pass as it did at baseline. T022 will be re-verified after that.

## Launcher notification (post-US3)

Attempted 2026-10-13 after T021: `agent_observe.list_agents()` still does NOT list
`spec009-launcher-2026-10-12`; `agent_message.send(..., receiver_name=
'spec009-launcher-2026-10-12')` failed with `RuntimeError: No sibling matches`, and
there is no parent route (`No parent matches the current agent`). **Delivery failed** —
the status summary is retained here (see the T022 section above for the environmental
blocker and the exact human action needed). The human can also read this file directly.


## T022 resolution + T023 + T024 (final)

- **T022 RESOLVED**: the human restarted the llama.cpp endpoint with the approved
  large context (verified n_ctx = 65536 via /props and /v1/models meta). The F10 live
  test passes again (42.8s), and the full gate is green:
  `pytest -q` = **500 passed, 0 failed** (130.94s) — 417 pre-existing + 83 new tests.
  Commit bcc466f.
- **T023 (artifact pinning, SC-001)**: recomputed SHA-256 of
  `data/raw/tickets_texts.jsonl` = `72c96e92...f0ed` — equals
  `texts-manifest.json.artifact_sha256` AND
  `artifacts/import-manifest.json.generated_texts.artifact_sha256`;
  `generated_texts.texts_manifest_sha256` also matches. Both files are committed to
  Git (`git ls-files --error-unmatch` OK) and byte-stable (working-tree
  `git hash-object` == `git rev-parse HEAD:` object `79430b67`). Commit bcc466f.
- **T024**: this report finalized.

## Final validation summary

| Gate | Command | Result |
|---|---|---|
| Baseline | `pytest -q` (T001) | 417 passed, 0 failed |
| Unit | `pytest tests/unit/ -q` | 153 passed |
| US1 artifact | `python scripts/validate_ticket_texts.py` | exit 0, all 7 checks, 2057 entries |
| US2 import | `pytest tests/integration/test_ticket_texts_import.py -q` | 8/8 |
| Feature-001 discipline | `pytest tests/integration/test_database_initialization.py tests/integration/test_database_import.py -q` | 16/16 |
| US3 exposure | `pytest tests/integration/test_graphjin_ticket_texts.py -q` | 6/6 |
| Security posture | `pytest tests/security/ -q` | 94/94 |
| **Full gate (SC-005)** | `pytest -q` | **500 passed, 0 failed** |

## Success-criteria mapping

- **SC-001** (artifact integrity): pinned + committed; SHA-256 stable and cross-checked
  in both manifests (T023). Any change = new artifact_version + full regeneration.
- **SC-002** (validation gate): deterministic suite exit 0, 100% of checks on 2057/2057
  (T013); NULL rule 250 open / 1807 closed.
- **SC-003** (resume reliability): T011 interrupted-and-resumed sample completed 25/25
  unique; the full run itself resumed from checkpoints after external interruptions
  (SIGTERM, deterministic batch failure) with exactly-once coverage.
- **SC-004** (provenance completeness): texts-manifest records model ID, llama.cpp
  version ("unreported"), temperature 0, seed 20261012, prompt_version "1", dspy 3.4.0,
  script + module hashes, batch_config, row_count, output SHA-256, created_at.
- **SC-005** (zero regression): full suite 500/500 (417 pre-existing pass unchanged).
- **SC-006** (governed exposure): 3 fields selectable (100-row limit), is-null on
  resolution_notes = 250 open tickets, 100% of write attempts rejected with zero DB
  changes (T019-T021).
- **SC-007** (human gate): T014 approved by Pal Majoros 2026-10-13 (commit c09cfdb)
  after per-category review (all 5 categories, open+closed); import enforced
  `human_review.approved == true`.

## Known limitations (final)

- llama.cpp build version is unreported by the endpoint (recorded as such).
- Byte-identical cross-environment regeneration is NOT claimed (spec Assumptions):
  governance = strict per-entry validation + deterministic suite + artifact pinning
  with checksums + full-version regeneration only.
- The all-open-composition failure mode (model confuses ticket_ids across similar
  open tickets) may recur on regeneration; batch-size 4 + checkpoint/resume mitigated
  it this run; zero-tolerance acceptance caught every case.
- Category-consistency is a deterministic lexicon check (mechanical topic
  consistency), not literary quality judgment — deep review was the human MANUAL GATE.
- GraphJin v3 (default_block + public_tables) gates TABLES; the policies.yml columns
  block is declarative — column-level read restriction is not enforced by this
  GraphJin version. The explicit allowlist is accurate; writes remain blocked at both
  the GraphJin access layer and the PostgreSQL read-only role.

## Feature status

**COMPLETE.** All 24 tasks done; the T014 MANUAL GATE was approved by the human;
the full validation gate is green (500/500). The three synthetic text fields are
generated, validated, pinned, imported, and exposed read-only through the governed
query layer, ready for the follow-up hybrid-search feature.
