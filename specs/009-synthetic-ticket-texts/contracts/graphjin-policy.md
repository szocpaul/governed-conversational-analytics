# Contract: GraphJin Policy Change (read-only exposure)

**File**: `graphjin/config/policies.yml` — `tickets` table allowlist gains
exactly three columns, nothing else changes:

```yaml
  - name: tickets
    schema: itsm
    table: tickets
    source: default
    read_only: true
    columns:
      # ... all 19 existing columns unchanged ...
      - name: short_description   # GENERATED (feature 009)
      - name: description         # GENERATED (feature 009)
      - name: resolution_notes    # GENERATED (feature 009)
```

## Guarantees (verified by tests/integration/test_graphjin_ticket_texts.py)

- The three fields are selectable through the governed GraphQL endpoint,
  alone and combined with existing filters (e.g. priority, is-null on
  resolution_notes returning exactly the 250 open tickets).
- Existing limits unchanged: `default_limit: 100` cap still applies.
- Writes stay blocked at BOTH layers: GraphJin `read_only: true` +
  `access.write/delete: blocked` config AND the PostgreSQL
  `itsm_readonly` role; INSERT/UPDATE/DELETE/TRUNCATE/CREATE/ALTER/DROP
  attempts fail with zero database changes (existing security tests plus
  the new exposure test re-verify).
- No blocklist interaction: the new column names contain no blocked
  tokens (password/secret/token/encrypted).
- `graphjin/config/dev.yml` needs NO change (`public_tables` already lists
  `tickets`).
