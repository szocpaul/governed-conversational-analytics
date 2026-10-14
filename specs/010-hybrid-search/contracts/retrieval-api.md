# Contract: Governed Hybrid Retrieval (application-layer, read-only)

**Module**: `app/ai/retrieval.py` (runtime; called by the planner as an opt-in
governed tool). NOT through GraphJin (human decision 1, research R1).

## Request shape (typed, pydantic-validated)

```json
{
  "mode": "about" | "similar",
  "query_text": "<natural-language content query>",   // mode=about
  "ticket_id": 847203,                                 // mode=similar
  "limit": 10
}
```

- `mode` selects the retrieval intent: `about` (lexical + semantic over the
  query text) or `similar` (semantic similarity to a reference ticket).
- `limit` is clamped to the enforced result limit (default 10, hard cap
  recorded; never exceeds the governed maximum).
- No field selection is exposed: the searchable fields are fixed to the
  allowlist (the three generated text fields). Any attempt to target a
  non-allowlisted field is rejected by the validator.

## Response shape

```json
{
  "ticket_ids": [847210, 847315],
  "scores": [0.0321, 0.0319],
  "trace": [{"event": "retrieval", "ticket_ids": [847210, 847315], "mode": "about"}]
}
```

- `ticket_ids` ranked by fused RRF score (k=60) DESC, tie-break ticket_id ASC;
  deterministic for identical inputs.
- `scores` are the fused RRF scores, same order.
- `trace` is sanitized: exactly the ticket_ids that entered the model's
  context; NEVER credentials, endpoint details, SQL text, or prompts.

## Governance guarantees (verified by tests)

- **Read-only**: connects as the `itsm_readonly` role (SELECT only,
  statement_timeout 5s). INSERT/UPDATE/DELETE/TRUNCATE/CREATE/ALTER/DROP
  attempts fail with zero database changes.
- **Allowlist**: only the three generated text fields are searchable; the
  allowlist is fixed in code, not model-controllable.
- **Result limit**: enforced; the response never exceeds the governed maximum.
- **No arbitrary SQL**: the model never emits SQL; the channel issues a fixed,
  parameterized statement set (lexical ts_rank, semantic cosine, RRF fusion)
  with the query text / reference embedding as bound parameters only.
- **Determinism**: identical requests produce identical fused rankings.
- **Trace hygiene**: the trace contains no credentials, private endpoint
  details, complete prompts, or prohibited data.

## Fusion (research R8)

```text
lexical:  rank by ts_rank(fts, plainto_tsquery('english', :q)) DESC
semantic: rank by embedding <=> :qvec ASC            (cosine distance)
fused:    score(t) = sum_over_sides( 1 / (60 + rank_side(t)) )   // missing side = 0
order:    score DESC, ticket_id ASC
```

For `mode=similar`, the reference ticket's stored embedding is the semantic
query vector; the lexical side uses the reference ticket's text.
