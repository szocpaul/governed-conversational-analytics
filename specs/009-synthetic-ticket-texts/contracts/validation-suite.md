# Contract: Deterministic Ticket-Text Validation Suite

**Script**: `scripts/validate_ticket_texts.py` (offline, NO model calls;
stdlib only)

## Synopsis

```bash
python scripts/validate_ticket_texts.py [--input PATH] [--tickets PATH]
    [--report PATH]
```

Defaults: `--input data/raw/tickets_texts.jsonl`,
`--tickets data/raw/tickets.csv`, `--report` optional JSON report output
(human-readable summary always on stdout).

## Checks (all deterministic, all pass/fail — research R5)

| # | Check | Pass condition |
|---|---|---|
| 1 | Schema + coverage | Every line parses to the entry schema; ticket_ids == pinned 2057 ids, each exactly once |
| 2 | Non-empty fields | No empty/whitespace strings; no `{...}` slot markers |
| 3 | Length limits | short_description: 1 sentence, <= 100 chars; description: 2-4 sentences, <= 600 chars; resolution_notes: 1-3 sentences, <= 450 chars when present (sentence = `[.!?]`-terminated segment) |
| 4 | English-only | >= 95% printable ASCII per field + >= 1 English function word per sentence |
| 5 | Secrets/PII scan | No credential patterns, API-key shapes, PEM headers, e-mails, phone numbers, IPv4 addresses |
| 6 | Category consistency | >= 1 lexicon keyword of the ticket's own sub_category present; no exclusive-conflict keyword of other categories |
| 7 | NULL rule | resolution_notes null <=> ticket open (250 open / 1807 closed against pinned tickets.csv) |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | 100% of checks pass (artifact is a release candidate for human review) |
| 1 | Any check fails; report lists every violation (ticket_id, check, detail), capped readably |

## Consumers

- Maintainer gate before human review (quickstart step 3).
- Unit tests (`tests/unit/test_ticket_texts_validation.py`) reuse the same
  check functions with canary inputs.
- Optionally re-run by the human reviewer; result recorded into
  `texts-manifest.json.validation`.
