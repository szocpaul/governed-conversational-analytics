# Runner Report: Feature 001 — Governed ITSM Data Foundation

**Date**: 2026-10-09
**Scope**: automatable tasks T001–T010. T011 is a MANUAL GATE and was NOT touched.

## 1. Completed task IDs

T001, T002, T003, T004, T005, T006, T007, T008, T009, T010 — all complete,
each with tests written first and observed failing before implementation.

## 2. Incomplete or blocked task IDs

None. T011 (MANUAL GATE) remains unchecked by design — human review required.

## 3. Files changed

- `compose.yml` — pinned services (postgres:16.10-alpine, dosco/graphjin:3.21.6),
  named volume, health check, GraphJin port 8081 (host 8080 was occupied by an
  existing sshd tunnel)
- `.env.example`, `.env` (gitignored), `.gitignore`
- `database/bootstrap.sql`, `database/schema.sql`, `database/roles.sql`
- `scripts/initialize_database.py`, `scripts/import_dataset.py`, `scripts/reset_database.py`
- `data/raw/merchants.csv`, `data/raw/agents.csv`, `data/raw/tickets.csv`,
  `data/raw/LICENSE` (immutable, mode 0444)
- `graphjin/config/dev.yml`, `graphjin/config/policies.yml`
- `tests/conftest.py`
- `tests/integration/test_postgres_service.py` (3 tests)
- `tests/integration/test_database_initialization.py` (8 tests)
- `tests/integration/test_database_import.py` (8 tests)
- `tests/integration/test_graphjin_queries.py` (6 tests)
- `tests/security/test_read_only_access.py` (14 tests)
- `tests/integration/test_foundation_smoke.py` (1 test)
- `artifacts/import-manifest.json`
- `specs/001-governed-itsm-data-foundation/quickstart.md`
- `README.md`
- `specs/001-governed-itsm-data-foundation/tasks.md` (T001–T010 marked [X])

## 4. Commits created

- `f3fc440` T001-T006: pinned dataset, PostgreSQL service, schema, roles, validated atomic import, reset
- `284777d` T007-T008: governed GraphJin read-only query surface
- `f663814` Ignore GraphJin container-managed state directory
- `915194f` T009-T010: foundation smoke test, validation gates, quickstart and README

## 5. Pinned dependency versions

- PostgreSQL image: `postgres:16.10-alpine`
  (digest sha256:029660641a0cfc575b14f336ba448fb8a75fd595d42e1fa316b9fb4378742297)
- GraphJin image: `dosco/graphjin:3.21.6` (server reports version 3.21.6,
  commit b8c6bbbafcd95c8ae99bb71eee88508b95a97414, Go 1.25.5)
- Python: 3.12.3 (system)
- psycopg: 3.3.6 (+ psycopg-binary 3.3.6, typing-extensions 4.16.0)
- pytest: 9.0.3
- Docker: 29.8.0; Docker Compose: v5.5.1

Note: the plan said "GraphJin v3" without an exact tag; `v3.0.35` does not
exist on Docker Hub, so the current stable v3 tag `3.21.6` was pinned.

## 6. Dataset provenance

- Source: https://github.com/drapertoby/itsm-ticket-dataset
- Pinned commit SHA: `cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`
  (re-resolved via GitHub API at import time; matches the expected value)
- License: MIT (verified via GitHub license API and `data/raw/LICENSE`,
  copyright drapertoby); attribution preserved in the manifest and README
- SHA-256 checksums:
  - merchants.csv: `4356ce83aa038a3c1e58b4d54c2edcdf04590b2ed4ac22b4cb68a950eec7b1bf`
  - agents.csv:    `2ff2a4b3370d439ad451e27ed32856d6c6d481621da71bcc4bc9a7c29e7408f5`
  - tickets.csv:   `768dc342aa1eb31a707a42510f69bc6699f214accee052822cf8470988912f15`
  - LICENSE:       `372a4354cc03df562a0f2f8db5501a0817134687ba527717bae9406836c697b6`
- Row counts: 112 merchants, 20 agents, 2057 tickets
- Full provenance and import results: `artifacts/import-manifest.json`

## 7. Validation commands and results

| Gate | Result |
|---|---|
| `pytest -q tests/integration/test_postgres_service.py` | 3 passed |
| `pytest -q tests/integration/test_database_initialization.py` | 8 passed |
| `pytest -q tests/integration/test_database_import.py` | 8 passed |
| `pytest -q tests/integration/test_graphjin_queries.py tests/security/test_read_only_access.py` | 20 passed |
| `pytest -q tests/integration/test_foundation_smoke.py` | 1 passed |
| `pytest -q` (aggregate) | 40 passed |

## 8. Security-effect and disclosure results

- PostgreSQL layer (`itsm_readonly` role): SELECT succeeds; INSERT, UPDATE,
  DELETE, TRUNCATE, CREATE, ALTER, DROP each fail with
  `psycopg.errors.InsufficientPrivilege` and ZERO database changes (verified
  by before/after snapshots of row counts and table count). Role-escalation
  attempts (`SET ROLE itsm_owner`, `ALTER ROLE ... SUPERUSER`) fail.
- GraphJin layer: insert/update/delete GraphQL mutations are rejected with
  errors and zero database changes. A SQL-injection attempt through a filter
  value had no effect. System catalogs (`pg_roles`, `pg_tables`) are not
  exposed. Result limit enforced (`default_limit: 100` against 2057 rows).
- Database-query timeout: `statement_timeout = 5s` set server-side on the
  `itsm_readonly` role (deterministic, independent of the application).

## 9. Known limitations

- GraphJin v3 does not expand `${VAR}` in config files and `GJ_*` env
  overrides cannot target `sources[]` array elements, so the local-demo
  read-only credentials appear literally in `graphjin/config/dev.yml`. These
  are the documented `.env.example` placeholder values, not real secrets.
  Non-local deployments must mount a different config. Documented in
  quickstart.md.
- The GraphJin distroless image has no shell/wget/curl, so no container-level
  health check is possible; readiness is verified by polling the GraphQL
  endpoint from the host (implemented in the test fixtures).
- GraphJin writes managed state (artifact SQLite, discovery snapshots) under
  `graphjin/config/.graphjin/`; the config mount is therefore writable by the
  container user (uid 65532) only in that subdirectory, and the directory is
  gitignored. Policy files remain owned by the host user and tracked in Git.
- Host port 8080 was already occupied (sshd tunnel), so GraphJin maps to
  host port 8081.
- `csat_score` in the source data is a normalized float in [0,1], not a 1–5
  integer; the schema stores it as `double precision CHECK (0..1)`.

## 10. Outstanding manual gates

- **T011 MANUAL GATE**: human reviewer must start the environment from a
  clean state, verify PostgreSQL health and database creation, review the
  import manifest and license attribution, check schema relationships and row
  counts, execute an authorized GraphJin query, and confirm rejected write
  operations. This task is unchecked and awaits human review.
