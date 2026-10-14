# Contract: Governed Hybrid Count Query

**Module**: `app/ai/retrieval.py` — a governed COUNT query alongside the
existing ranked-list query. Same guarantees: field allowlist, read-only
role, parameterized, sanitized trace.

## Match semantics (hybrid)

A ticket matches when EITHER side matches (counted once):

```text
lexical:   fts @@ plainto_tsquery('english', :q)
semantic:  (embedding <=> :qvec) <= :threshold
match  =   lexical OR semantic
```

- `:q` = the count query text (bound parameter).
- `:qvec` = the query text embedded by the pinned EmbeddingGemma-2 endpoint
  (bound parameter).
- `:threshold` = the calibrated semantic-match threshold from
  `count-threshold.json` (bound parameter).

## SQL shape (verified live against pgvector/pgvector:pg16)

```sql
SELECT count(*) AS match_count
FROM itsm.tickets
WHERE fts @@ plainto_tsquery('english', %s)
   OR (embedding <=> %s::vector) <= %s;
```

Plus a separate small LIMITed selection (<= 5) over the SAME match condition
for the example ticket_ids used in grounding.

## Guarantees (verified by tests)

- **True total**: NO LIMIT on the count; never capped by the retrieval
  result limit (no undercount).
- **Allowlist**: only the three generated text fields are searched (via the
  `fts` column and the `embedding` column, both built from them).
- **Read-only**: connects as `itsm_readonly` (SELECT only, statement_timeout
  5s); writes/DDL rejected with zero database changes.
- **No arbitrary SQL**: the query is a fixed statement with bound parameters
  only; the model never emits SQL.
- **Threshold required**: if the threshold is absent or uncalibrated, the
  count path stops and reports (never a hardcoded default).
- **Sanitized trace**: the count + up to 5 example ids; no credentials,
  endpoint details, SQL text, or prompts.
