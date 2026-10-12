# Quickstart Validation: Synthetic Ticket Texts

**Feature**: 009-synthetic-ticket-texts | **Date**: 2026-10-12

Runnable end-to-end validation for the feature. Contracts referenced:
[generator-cli](contracts/generator-cli.md),
[validation-suite](contracts/validation-suite.md),
[artifact-schemas](contracts/artifact-schemas.md),
[graphjin-policy](contracts/graphjin-policy.md).

## Prerequisites

1. Stack healthy: `docker compose up -d` (PostgreSQL 16.10-alpine,
   GraphJin 3.21.6), `.env` configured per `.env.example` with the pinned
   local LLM endpoint values.
2. Pinned data verified: `python scripts/import_dataset.py` succeeds on the
   current dataset (checksums match `artifacts/import-manifest.json`).
3. Endpoint verified: the exact pinned model ID responds (same discipline
   as `artifacts/llm-preflight.json`; the generator re-verifies itself).
4. Schema updated: `python scripts/initialize_database.py` (idempotent;
   adds the three generated columns).

## Step 1 — Generation dry-run on a small sample

```bash
python scripts/generate_ticket_texts.py --sample 10 --output /tmp/tickets_texts_sample.jsonl
```

Expected: exit 0; 10 validated entries (2 batches of 5) in tickets.csv
order; open tickets in the sample have `"resolution_notes": null`; stderr
log shows endpoint verification, batches, retries used.

## Step 2 — Resume test (simulated interruption)

```bash
python scripts/generate_ticket_texts.py --sample 25 --output /tmp/tickets_texts_resume.jsonl &
# kill the process after ~2 batches (Ctrl-C or kill <pid>)
ls artifacts/tickets_texts.checkpoint.jsonl   # checkpoint exists
python scripts/generate_ticket_texts.py --sample 25 --output /tmp/tickets_texts_resume.jsonl
```

Expected: the second run RESUMES from the checkpoint (log shows accepted
ticket_ids loaded, remaining batches only), completes with exactly 25
unique entries, never restarting from scratch, never skipping. (Unit tests
cover the same semantics hermetically with a stubbed LM.)

## Step 3 — Full generation

```bash
python scripts/generate_ticket_texts.py
```

Expected: exit 0 after ~412 batches; `data/raw/tickets_texts.jsonl` (2057
lines) + `data/raw/texts-manifest.json` written; checkpoint deleted;
manifest records model ID, versions, seed, prompt version, batch config,
hashes, created_at; `human_review.approved` is `false`.

## Step 4 — Deterministic validation suite

```bash
python scripts/validate_ticket_texts.py
```

Expected: exit 0 — all 7 checks pass (schema+coverage 2057/2057 exactly
once, non-empty, lengths, English-only, secrets/PII scan, category
consistency, NULL rule 250/1807).

## Step 5 — MANUAL GATE: human data-quality review (HUMAN ONLY)

The human reviews per-category samples (all 5 categories, e.g. 5 tickets
each incl. open and closed) and, only if satisfied, sets
`human_review.approved: true` with reviewer/date/notes in
`data/raw/texts-manifest.json`. **Agents must never set this marker.** The
import refuses to proceed without it (Step 6 fails with a clear error if
the marker is absent).

## Step 6 — Atomic import

```bash
python scripts/import_dataset.py
```

Expected: exit 0; single transaction upserts pinned data + the three
generated columns for all 2057 tickets; `artifacts/import-manifest.json`
gains the `generated_texts` key; re-running is idempotent (identical
result). Reset-path check: `python scripts/reset_database.py && python
scripts/initialize_database.py && python scripts/import_dataset.py`
reproduces the same state.

## Step 7 — Governed read test

Restart GraphJin (config changed), then through the app/GraphQL endpoint:

- Select `short_description`, `description`, `resolution_notes` for a
  handful of tickets (respecting the 100-row limit).
- Filter `resolution_notes` is-null -> exactly 250 tickets (the open ones).
- Attempt any write/mutation -> rejected; database unchanged.

Expected: reads succeed; all writes fail with zero database changes;
existing security tests (`tests/security/`) still pass.

## Step 8 — Full regression

```bash
pytest -q
```

Expected: all pre-existing 417 tests pass plus the new unit/integration
tests of this feature; no failures introduced.

## Done criteria mapping

Steps 1-4 -> SC-002, SC-003, SC-004; Step 5 -> SC-007 (MANUAL GATE);
Step 6 -> FR-014/FR-015 + import manifest extension; Step 7 -> SC-006;
Step 8 -> SC-005. Artifact checksum stability (SC-001) is verified by
re-checking `artifact_sha256` after approval.
