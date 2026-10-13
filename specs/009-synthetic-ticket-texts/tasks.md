# Tasks: Synthetic Ticket Texts

**Input**: Design documents from `/specs/009-synthetic-ticket-texts/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — AGENTS.md requires tests before implementation, with
the expected failure observed first. Unit tests stub the LM
(`dspy.utils.DummyLM`); the shipped artifact only ever comes from a real
recorded run (research R11).

**Organization**: Tasks are grouped by user story (US1 generation pipeline
= P1, US2 database import = P2, US3 read-only exposure = P3). US2 hard-depends
on the US1 artifact AND the MANUAL GATE (T014); US3 hard-depends on US2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 — maps to spec.md user stories
- All file paths are repository-relative

## Phase 1: Setup

- [x] T001 Record the pre-implementation baseline in `specs/009-synthetic-ticket-texts/runner-report.md` (skeleton): current git commit + working-tree state, and `pytest -q` result (expect 417 passed, 0 failed). Do not overwrite unrelated user changes.
- [x] T002 [P] LLM preflight for generation per the `app/ai/llm.py` discipline: call `GET /v1/models` on the configured endpoint, verify the exact pinned model ID is loaded, run one deterministic seeded chat-completion smoke request (temperature 0, cache false), and save non-secret metadata (endpoint reachability, exact model ID, seed acceptance) to `artifacts/llm-preflight-009.json`. STOP AND REPORT on any mismatch — no fallback model.
- [x] T003 [P] Add the transient generation state to `.gitignore`: `artifacts/tickets_texts.checkpoint.jsonl` and local sample outputs (`/tmp` usage needs no rule; document the checkpoint rule in the file comment).

## Phase 2: Foundational (tests first — BLOCKS all user stories)

- [x] T004 Write `tests/unit/test_ticket_texts_validation.py`: canary-driven tests for all 7 deterministic checks in `specs/009-synthetic-ticket-texts/contracts/validation-suite.md` — (1) schema + coverage (small fixture: every ticket exactly once, duplicates/missing rejected), (2) non-empty fields + `{...}` slot-marker rejection, (3) length limits (short_description exactly 1 sentence and <= 100 chars; description 2-4 sentences and <= 600 chars; resolution_notes 1-3 sentences and <= 450 chars; `[.!?]` sentence counting), (4) English-only heuristic (>= 95% printable ASCII + function-word presence; non-English canary fails), (5) secrets/PII canary scan (password=, bearer token, API-key shape, PEM header, e-mail, phone, IPv4 all rejected), (6) category-consistency lexicon (own-sub_category keyword required; exclusive other-category keyword e.g. "login" on a Payments ticket rejected), (7) NULL rule against the pinned `data/raw/tickets.csv` (resolution_notes null exactly for the 250 open tickets, present for the 1807 closed). Run `pytest tests/unit/test_ticket_texts_validation.py -q` and observe FAIL (`scripts/validate_ticket_texts.py` missing).
- [x] T005 [P] Write `tests/unit/test_text_generation_program.py` with a stubbed LM (`dspy.utils.DummyLM`, scripted JSON responses): valid 5-ticket batch accepted (pydantic `TicketTextEntry` list, exact ticket_id set, same order); malformed JSON rejected; ticket_id set mismatch (missing, extra, duplicate) rejected; `resolution_notes` non-null for an open ticket rejected; null for a closed ticket rejected; batch retried on failure up to `--max-retries` (default 2) then raises. Run and observe FAIL (`app/ai/text_generation.py` missing).
- [x] T006 [P] Write `tests/unit/test_ticket_texts_checkpoint.py`: checkpoint append after each accepted batch; load + resume continues with remaining batches in pinned `tickets.csv` order and never re-accepts or skips a ticket (simulated interruption: partial checkpoint -> resume -> exactly-once coverage); torn final line / corrupt JSON fails loudly; checkpoint containing an unknown ticket_id fails loudly; successful completion deletes the checkpoint; `--fresh` discards it explicitly. Run and observe FAIL (`scripts/generate_ticket_texts.py` missing).

## Phase 3: User Story 1 — Governed LLM text generation with strict validation (P1) 🎯 MVP

**Goal**: A maintainer runs one explicit offline command that produces a
strictly validated, provenance-recorded text artifact for all 2057 tickets
via the pinned local model, with checkpoint/resume and fail-loud behavior.

**Independent Test**: Run generation twice-interrupted (resume) on a sample,
then full; the deterministic validation suite passes 100% on the artifact
and the manifest is complete — no database involved.

- [x] T007 [P] [US1] Implement `app/ai/text_generation.py` per research R1/R4: strict pydantic `TicketTextEntry` (`ticket_id: int`, `short_description: str`, `description: str`, `resolution_notes: str | None` — key always present, null allowed); `GenerateTicketTexts(dspy.Signature)` whose docstring is the versioned instruction (field shapes verbatim from the data model: short_description exactly 1 sentence <= 100 chars targeting ~80 and naming the problem + key detail; description 2-4 sentences <= 600 chars with reporter context/scope/trigger/impact and priority-appropriate wording; resolution_notes 1-3 sentences <= 450 chars with root cause/fix/verification, null exactly for open tickets; English only; consistent with the given category/sub_category; built only from the provided structured fields); module-level `PROMPT_VERSION = "1"`; a batch program running `dspy.Predict` under an explicit `dspy.JSONAdapter()` with per-batch zero-tolerance acceptance (parse succeeds; entry ticket_id set equals input set exactly, same count, no duplicates; per-entry null rule) and bounded identical-request retries then a loud exception. Offline module only — not imported by the runtime query path. Iterate until T005 passes.
- [x] T008 [P] [US1] Implement `scripts/validate_ticket_texts.py` per contracts/validation-suite.md: stdlib-only CLI (`--input`, `--tickets`, `--report`; exit 0 on 100% pass, exit 1 with a per-violation report otherwise) implementing the 7 checks tested in T004, including the hand-maintained 20-pair category lexicon (deterministic, reviewable constants). Iterate until T004 passes.
- [x] T009 [US1] Implement `scripts/generate_ticket_texts.py` per contracts/generator-cli.md (depends on T007): verify pinned `data/raw/tickets.csv` SHA-256 against `artifacts/import-manifest.json` before any model call; verify endpoint + exact pinned model ID via `app/ai/llm.py` (exit 2 on mismatch/unreachable/seed rejection); run seeded batches (default 5) in pinned CSV order with bounded retries (default 2, then exit 1 naming the failing batch); append-only checkpoint at `artifacts/tickets_texts.checkpoint.jsonl` with resume-by-default and `--fresh`; on completion write `data/raw/tickets_texts.jsonl` (2057 lines, CSV order, all four keys per line) and `data/raw/texts-manifest.json` (schema per contracts/artifact-schemas.md, `human_review.approved: false`), then delete the checkpoint; never write to the database; never modify pinned raw files. Iterate until T006 passes.
- [x] T010 [US1] Live sample dry-run (quickstart step 1): `python scripts/generate_ticket_texts.py --sample 10 --output /tmp/tickets_texts_sample.jsonl`, then `python scripts/validate_ticket_texts.py --input /tmp/tickets_texts_sample.jsonl` (sample-aware run), and manually inspect the 10 entries for shape sanity (open tickets null, lengths, category fit). Record the outcome in the runner notes. Any shape problem is fixed in the signature/validator (T007/T008), never by hand-editing output.
- [x] T011 [US1] Live resume test (quickstart step 2): start `--sample 25`, interrupt after ~2 batches, confirm `artifacts/tickets_texts.checkpoint.jsonl` exists, re-run and confirm resume-from-checkpoint (accepted ids loaded, remaining batches only) completing with exactly 25 unique entries. Record the outcome.
- [x] T012 [US1] Full live generation run (quickstart step 3): `python scripts/generate_ticket_texts.py` — expect ~412 batches; verify exit 0, 2057-line artifact, manifest complete (model ID, llama.cpp version or "unreported", temperature 0, seed, prompt version, DSPy version, script + module hashes, batch config incl. retries used, created_at), checkpoint deleted. Record runtime (observational only).
- [x] T013 [US1] Validate the full artifact (quickstart step 4): `python scripts/validate_ticket_texts.py` MUST exit 0 — all 7 checks, 2057/2057 coverage, NULL rule 250/1807. On any failure, fix at source (signature, generator, or validator logic) and regenerate per the full-run policy; never patch the artifact by hand. Record the validation result into `data/raw/texts-manifest.json` (`validation` block).
- [x] T014 MANUAL GATE — Human data-quality review (quickstart step 5): the HUMAN reviews per-category samples (all 5 categories, open and closed tickets) and, only if satisfied, sets `human_review.approved: true` with `reviewer`, `reviewed_at`, `sample_notes` in `data/raw/texts-manifest.json` and ticks this box. DO NOT let an automated agent set the marker, tick, approve, or bypass this gate. US2 (import) MUST NOT start its live import before this box is ticked.

## Phase 4: User Story 2 — Database import of generated fields with provenance (P2)

**Goal**: The approved pinned artifact lands in `itsm.tickets` as three
generated columns via the existing atomic, idempotent import, with
provenance recorded in the import manifest.

**Independent Test**: Reset -> initialize -> import; all 2057 tickets have
the three columns (resolution_notes NULL exactly for the 250 open tickets),
pinned columns byte-identical to source, re-import idempotent.

- [x] T015 [US2] Write `tests/integration/test_ticket_texts_import.py`: after import, all 2057 tickets have short_description/description populated and resolution_notes populated exactly for the 1807 closed tickets (NULL for the 250 open); spot-check pinned columns against `data/raw/tickets.csv` (unchanged); re-import is idempotent (identical counts and content); import with a manifest copy lacking `human_review.approved: true` (temporary fixture copy — the real manifest is never modified by the test) fails with zero database changes; a tampered artifact (checksum mismatch) fails with zero database changes; `artifacts/import-manifest.json` gains the `generated_texts` key per contracts/artifact-schemas.md while `dataset` and `import` keep their shape (feature-001 compatibility). Run and observe FAIL (import does not load texts yet).
- [x] T016 [US2] Update `database/schema.sql` per research R6: add `short_description text NULL`, `description text NULL`, `resolution_notes text NULL` to the `itsm.tickets` CREATE TABLE with `-- GENERATED (feature 009, synthetic text from pinned artifact data/raw/tickets_texts.jsonl)` comments, plus three idempotent `ALTER TABLE itsm.tickets ADD COLUMN IF NOT EXISTS ...` statements after the CREATE TABLE. Run `python scripts/initialize_database.py` and verify the columns exist. No new indexes.
- [x] T017 [US2] Extend `scripts/import_dataset.py` per research R7 (depends on T016): inside the SAME single transaction — verify artifact SHA-256 against `data/raw/texts-manifest.json`, ticket_id coverage == pinned 2057, NULL rule against tickets.csv, and `human_review.approved == true` (refuse loudly otherwise); upsert the three generated columns per ticket (`ON CONFLICT (ticket_id) DO UPDATE` of the generated columns only); post-import count + NULL-rule checks inside the transaction; on success extend `artifacts/import-manifest.json` with the `generated_texts` key (paths, both SHA-256 hashes, artifact_version, row_count, human_review record, imported_at) without altering existing keys. Iterate until T015 passes.
- [ ] T018 [US2] Exercise the clean reset path end-to-end (quickstart step 6): `python scripts/reset_database.py && python scripts/initialize_database.py && python scripts/import_dataset.py` reproduces the full state (2057 tickets, 3 columns populated, NULL rule), and `pytest tests/integration/test_database_initialization.py tests/integration/test_database_import.py -q` stays green (feature-001 discipline unbroken).

## Phase 5: User Story 3 — Read-only governed exposure of the new columns (P3)

**Goal**: Analysts can read the three generated fields through the governed
query layer; every write attempt stays rejected.

**Independent Test**: Governed GraphQL selects of the three fields succeed
(incl. is-null on resolution_notes = 250); all write attempts fail with
zero database changes.

- [ ] T019 [US3] Write `tests/integration/test_graphjin_ticket_texts.py` per contracts/graphjin-policy.md: governed GraphQL select of `short_description`, `description`, `resolution_notes` (with the 100-row limit respected); is-null filter on resolution_notes returns exactly 250 tickets; combined filter (e.g. priority + field selection) works; INSERT/UPDATE/DELETE attempts against tickets are rejected with zero database changes. Run against the live stack and observe FAIL (columns not yet allowlisted).
- [ ] T020 [US3] Update `graphjin/config/policies.yml`: add exactly `short_description`, `description`, `resolution_notes` to the tickets column allowlist (with `# GENERATED (feature 009)` comments); no other config change (`dev.yml` untouched). Restart GraphJin and iterate until T019 passes.
- [ ] T021 [US3] Run `pytest tests/security/ -q` (incl. `tests/security/test_read_only_access.py` and `tests/security/test_authorization.py`) and confirm the entire security posture is unchanged (read-only enforcement, authorization, limits/timeouts, redaction) with the new columns exposed.

## Phase 6: Polish & Validation

- [ ] T022 Run the full validation gate set from `specs/009-synthetic-ticket-texts/quickstart.md` steps 1-8: `pytest -q` green (all 417 pre-existing + new tests, SC-005); full artifact validation exit 0; governed read checks pass. Fix any failure at its source.
- [ ] T023 Verify artifact pinning (SC-001): recompute SHA-256 of `data/raw/tickets_texts.jsonl` and confirm it equals `texts-manifest.json.artifact_sha256` and the `generated_texts` record in `artifacts/import-manifest.json`; confirm the approved artifact is committed to Git and byte-stable across a fresh checkout/read.
- [ ] T024 Complete `specs/009-synthetic-ticket-texts/runner-report.md` per the AGENTS.md Required Final Report: completed/blocked task IDs, files changed, commits, exact pinned versions, validation commands with exact results, live-generation summary (batches, retries, runtime as observational), security-effect and disclosure results, MANUAL GATE evidence (reviewer, date), known limitations.

## Dependencies

```text
T001 -> T002/T003 (baseline first; preflight + gitignore parallel)
T004/T005/T006 parallel (different test files) — all must FAIL before implementation
T004 -> T008; T005 -> T007; T006 -> T009; T007 -> T009 (generator uses the program)
T009 -> T010 -> T011 -> T012 -> T013 (sample -> resume -> full run -> validation)
T013 -> T014 (MANUAL GATE: human review of the validated artifact)
T014 -> T015/T016/T017 -> T018 (import only after human approval)
T016 -> T017 (import needs the columns)
T017 -> T019 -> T020 -> T021 (exposure needs imported data; policy change; security re-check)
T022/T023 depend on all stories; T024 last
```

User stories are NOT parallel here: US2 consumes the US1 artifact and the
MANUAL GATE; US3 consumes the US2 database state. Within phases, the marked
[P] tasks are parallel.

## Parallel Execution Examples

- T004, T005, T006 written in parallel (three different test files).
- T007 (`app/ai/text_generation.py`) and T008 (`scripts/validate_ticket_texts.py`)
  in parallel after their tests exist.
- T002 and T003 in parallel during Setup.

## Implementation Strategy

1. Setup + Foundational (T001-T006): baseline, preflight, failing tests.
2. MVP = Phase 3 (US1): the validated, provenance-recorded artifact alone
   delivers the core value — STOP at the MANUAL GATE (T014).
3. Increment: US2 (import, only after the human gate), then US3 (exposure).
4. Polish: gates + pinning verification + runner report.

## Notes

- [P] tasks = different files, no dependencies
- Tests MUST be observed failing before their implementation task starts
- The generated artifact is NEVER hand-edited; fixes go to the signature,
  generator, or validator, followed by regeneration per the full-run policy
- Commit after each task or logical group; keep task IDs in commit messages
- The private LLM endpoint, credentials, and prompts must not appear in
  user-facing output, committed files, or traces
- STOP at T014 (MANUAL GATE) — the human reviews before any import
