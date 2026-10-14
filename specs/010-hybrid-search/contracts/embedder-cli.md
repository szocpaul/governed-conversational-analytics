# Contract: Embedding Generator CLI

**Script**: `scripts/generate_embeddings.py` (offline, maintainer-run; never
part of the runtime query path)

## Synopsis

```bash
python scripts/generate_embeddings.py [--output PATH] [--max-retries N]
    [--fresh] [--sample N]
```

## Inputs

| Source | Use |
|---|---|
| `data/raw/tickets_texts.jsonl` (pinned, feature 009) | Text input; SHA-256 verified against `data/raw/texts-manifest.json` before any embedding call |
| `data/raw/tickets.csv` (pinned) | Open/closed NULL rule for resolution_notes; SHA-256 verified against `artifacts/import-manifest.json` |
| `.env` (`EMBED_*`) | Embedding endpoint config; exact model ID verified via `GET /v1/models`; mismatch/unreachable/unsupported = exit 2, no fallback |
| `artifacts/tickets_embeddings.checkpoint.jsonl` | Resume state, loaded when present (unless `--fresh`) |

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--output PATH` | `data/raw/tickets_embeddings.jsonl` | Final artifact path (written only on completion) |
| `--max-retries N` | `2` | Bounded retries per failing ticket, then loud failure |
| `--fresh` | off | Discard any existing checkpoint and start over (explicit, logged) |
| `--sample N` | off | Embed only the first N tickets (dry-run/validation support); output to `--output` (use a non-default path); NO manifest approval flow applies |

## Behavior guarantees

- Per-ticket embedding in pinned tickets.csv order; per-ticket strict
  acceptance (dimension exactly 768, all values finite, research R5).
- Input text = concatenation of short_description + description +
  resolution_notes (available fields only for open tickets; never a
  placeholder), joined by a recorded separator constant.
- Checkpoint append after every accepted ticket; resume never restarts from
  scratch and never skips tickets; completed run covers every ticket exactly
  once (2057).
- On success: writes the artifact, writes `data/raw/embeddings-manifest.json`
  (schema: contracts/artifact-schemas.md), deletes the checkpoint. Prints row
  count, retries used, runtime.
- On any failure: non-zero exit, explicit stderr message naming the failing
  ticket/check; artifact NOT written; checkpoint preserved for resume.
- Never writes to the database; never touches pinned raw files.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Completed: artifact + manifest written |
| 1 | Embedding/validation failure (bad dimension after retries, checkpoint corruption, coverage mismatch, pinned-input checksum mismatch) |
| 2 | Endpoint/model verification failure (unreachable endpoint, model ID mismatch, embeddings route unsupported) |
