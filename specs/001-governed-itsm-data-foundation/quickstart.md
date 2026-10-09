# Quickstart: Governed ITSM Data Foundation

This feature provides a reproducible PostgreSQL data foundation built from a
pinned synthetic ITSM dataset, exposed only through a read-only,
policy-controlled GraphJin query surface.

## Prerequisites

- Docker with the Compose plugin (`docker compose`). On this machine Docker
  commands use passwordless sudo: `sudo -n docker ...`.
- Python 3.12+ with `psycopg` (`uv pip install --system --break-system-packages "psycopg[binary]"`).
- `pytest` for the validation gates.

## Configuration

1. Copy `.env.example` to `.env` and adjust only if needed. The default values
   are local-demo placeholders, not real secrets:

   ```bash
   cp .env.example .env
   ```

   | Variable | Purpose |
   |---|---|
   | `POSTGRES_USER` / `POSTGRES_PASSWORD` | owner role, used ONLY by the initialization/import scripts |
   | `POSTGRES_DB` | application database name (`itsm`) |
   | `POSTGRES_PORT` | host port for PostgreSQL (`5432`) |
   | `GRAPHJIN_DB_USER` / `GRAPHJIN_DB_PASSWORD` | read-only role used by the GraphJin runtime |
   | `GRAPHJIN_PORT` | host port for GraphJin (`8081`) |

## Startup

```bash
# Start PostgreSQL (pinned postgres:16.10-alpine) and wait for the health check
sudo docker compose up -d --wait postgres

# Create the application database, schema, tables, indexes, and roles (idempotent)
python3 scripts/initialize_database.py

# Validate and import the pinned dataset (atomic; updates artifacts/import-manifest.json)
python3 scripts/import_dataset.py

# Start the governed GraphJin query surface (pinned dosco/graphjin:3.21.6)
sudo docker compose up -d graphjin
```

GraphJin serves GraphQL at `http://127.0.0.1:8081/api/v1/graphql`.

Example authorized query:

```bash
curl -s -X POST http://127.0.0.1:8081/api/v1/graphql   -H "Content-Type: application/json"   -d '{"query":"{ tickets(limit: 3) { ticket_id priority merchants { merchant_name } } }"}'
```

## Health checks

- PostgreSQL: container health check via `pg_isready` (see `compose.yml`);
  `sudo docker compose ps` shows `healthy`.
- GraphJin: poll the GraphQL endpoint with `{ __typename }` until the response
  no longer contains a "not initialized" error (the distroless image has no
  shell, so there is no container-level health check).

## Reset procedure

Clean local reset (drops the application schema, keeps the service running):

```bash
python3 scripts/reset_database.py
python3 scripts/initialize_database.py
python3 scripts/import_dataset.py
```

Full reset including the persistent volume:

```bash
sudo docker compose down -v
sudo docker compose up -d --wait postgres
python3 scripts/initialize_database.py
python3 scripts/import_dataset.py
```

Reset plus reimport from the pinned source reproduces identical validated row
counts (112 merchants, 20 agents, 2057 tickets).

## Dataset provenance

- Source: <https://github.com/drapertoby/itsm-ticket-dataset>
- Pinned commit: `cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`
- License: MIT (copyright drapertoby), preserved in `data/raw/LICENSE`
- Raw files in `data/raw/` are immutable (read-only) and SHA-256 verified on
  every import. Checksums, attribution, and import results are recorded in
  `artifacts/import-manifest.json`.

## Schema

Schema `itsm`, created by `database/schema.sql`:

- `merchants` (`merchant_id` PK, `merchant_name`, `sector`, `tier`, `region`)
- `agents` (`agent_id` PK, `agent_name`, `tier`, `primary_category`,
  `shift_region`, `efficiency_multiplier`)
- `tickets` (`ticket_id` PK, `merchant_id` FK -> merchants,
  `assigned_agent_id` FK -> agents, category/sub_category, priority P1-P4,
  timestamps, SLA breach flags, reopen/incident flags, `csat_score`)

Indexes: `idx_tickets_merchant_id`, `idx_tickets_assigned_agent_id`,
`idx_tickets_priority`, `idx_tickets_category`, `idx_tickets_created_at`.

## Roles

- `itsm_owner`: owns the schema; used only by `scripts/initialize_database.py`
  and `scripts/import_dataset.py`.
- `itsm_readonly`: LOGIN role with CONNECT, schema USAGE, and SELECT only;
  write/DDL privileges explicitly revoked; `statement_timeout = 5s`. This is
  the ONLY role used by the GraphJin runtime.

## GraphJin configuration

- `graphjin/config/policies.yml`: blocklist, explicit entity allowlist
  (`merchants`, `agents`, `tickets`) with explicit field allowlists, and
  explicit relationships (`tickets.merchant_id -> merchants.merchant_id`,
  `tickets.assigned_agent_id -> agents.agent_id`).
- `graphjin/config/dev.yml`: inherits the policy; pins the PostgreSQL source
  (read-only, schema `itsm`), `default_limit: 100`, `default_block: true`,
  source access `read: public`, `write: blocked`, `delete: blocked`; MCP and
  the artifact store are disabled/not used for the runtime query path.

GraphJin v3 does not expand `${VAR}` in config files and `GJ_*` environment
overrides cannot target `sources[]` array elements, so the local-demo
read-only credentials appear literally in `dev.yml` (the same placeholder
values as `.env.example`). Non-local deployments must mount a different
config with their own credentials.

## Failure rules

- Import fails atomically (single transaction) on checksum mismatch, missing
  or duplicate business keys, unresolved foreign keys, or row-count mismatch.
  No partial data is committed and no replacement records are generated.
- Raw files are immutable; a checksum mismatch stops the import.
- GraphJin connects only as `itsm_readonly`; mutations and DDL are rejected
  at both the GraphJin policy layer and the PostgreSQL privilege layer.

## Validation gates

```bash
pytest -q tests/integration/test_postgres_service.py
pytest -q tests/integration/test_database_initialization.py
pytest -q tests/integration/test_database_import.py
pytest -q tests/integration/test_graphjin_queries.py tests/security/test_read_only_access.py
pytest -q tests/integration/test_foundation_smoke.py
```

or simply `pytest -q` for the full suite (40 tests).
