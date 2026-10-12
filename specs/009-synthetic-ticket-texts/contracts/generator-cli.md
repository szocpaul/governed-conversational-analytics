# Contract: Ticket-Text Generator CLI

**Script**: `scripts/generate_ticket_texts.py` (offline, maintainer-run; never
part of the runtime query path)

## Synopsis

```bash
python scripts/generate_ticket_texts.py [--output PATH] [--batch-size N]
    [--seed N] [--max-retries N] [--fresh] [--sample N]
```

## Inputs

| Source | Use |
|---|---|
| `data/raw/tickets.csv` (pinned) | Sole data input; SHA-256 verified against `artifacts/import-manifest.json` before any model call |
| `.env` (`LLM_*`) | Endpoint config; exact model ID verified via `GET /v1/models` (reuses `app/ai/llm.py`); mismatch or unreachable endpoint = exit 2, no fallback |
| `artifacts/tickets_texts.checkpoint.jsonl` | Resume state, loaded when present (unless `--fresh`) |

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--output PATH` | `data/raw/tickets_texts.jsonl` | Final artifact path (written only on completion) |
| `--batch-size N` | `5` | Tickets per model call (human-approved default; recorded in manifest) |
| `--seed N` | recorded constant | Seed passed to every model call; recorded in manifest |
| `--max-retries N` | `2` | Bounded retries per failing batch, then loud failure |
| `--fresh` | off | Discard any existing checkpoint and start over (explicit, logged) |
| `--sample N` | off | Process only the first N tickets (dry-run/validation support); output written to `--output` (use a non-default path) and NO manifest approval flow applies |

## Behavior guarantees

- Batches in pinned tickets.csv order; per-batch strict acceptance
  (schema + exact ticket_id set + per-entry rules, research R4).
- Checkpoint append after every accepted batch; resume never restarts from
  scratch and never skips tickets; completed run covers every ticket
  exactly once.
- On success: writes the artifact, writes `data/raw/texts-manifest.json`
  (schema: contracts/artifact-schemas.md) with `human_review.approved:
  false`, deletes the checkpoint. Prints row count, retries used, runtime.
- On any failure: non-zero exit, explicit stderr message naming the failing
  batch/check; artifact NOT written; checkpoint preserved for resume.
- Never writes to the database; never touches pinned raw files.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Completed: artifact + manifest written |
| 1 | Generation/validation failure (invalid entries after retries, checkpoint corruption, coverage mismatch, pinned-CSV checksum mismatch) |
| 2 | Endpoint/model verification failure (unreachable endpoint, model ID mismatch, seed-parameter rejection) |
