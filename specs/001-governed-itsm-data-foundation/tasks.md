# Tasks: Governed ITSM Data Foundation

**Spec**: `specs/001-governed-itsm-data-foundation/spec.md`  
**Plan**: `specs/001-governed-itsm-data-foundation/plan.md`  
**Tests**: Tests MUST be written first and observed failing before the corresponding implementation.

## Phase 1: Source Preflight and PostgreSQL Service

- [X] **T001 [P] [US1]** Verify the dataset repository `https://github.com/drapertoby/itsm-ticket-dataset`, resolve and record the exact commit SHA, verify the MIT license and attribution, calculate SHA-256 checksums, and download immutable `merchants.csv`, `agents.csv`, and `tickets.csv` into `data/raw/`. Store source metadata in `artifacts/import-manifest.json`. Stop and report if source, revision, license, or files cannot be verified.

- [X] **T002 [P] [US1]** Configure a pinned PostgreSQL service in `compose.yml` with a named persistent volume, database name, owner role, health check, initialization mount points, and environment-variable placeholders in `.env.example`. Create `tests/integration/test_postgres_service.py` first and verify that the service reaches healthy state and accepts a connection to the configured application database.

## Phase 2: Database Creation and Schema Initialization

- [X] **T003 [US1]** Write failing initialization tests in `tests/integration/test_database_initialization.py`, then create `database/bootstrap.sql` to create the application database when absent, and create `database/schema.sql` with the application schema, `merchants`, `agents`, and `tickets` tables, primary keys, foreign keys, required analytical fields, constraints, and indexes.

- [X] **T004 [US1]** Create `database/roles.sql` and `scripts/initialize_database.py` to apply `database/bootstrap.sql`, `database/schema.sql`, and `database/roles.sql` in a deterministic order. Initialization MUST be idempotent and safe to run more than once. Tests MUST verify that the database, schema, tables, indexes, owner role, and read-only role exist after initialization.

- [X] **T005 [US1]** Implement validation and normalized import in `scripts/import_dataset.py`. Verify source and imported row counts, required fields, timestamp and boolean conversion, non-null business keys, foreign-key integrity, and zero duplicate business keys. Update `artifacts/import-manifest.json` with import results and fail the import transaction atomically on validation errors.

- [X] **T006 [US1]** Add `scripts/reset_database.py` or an equivalent documented Docker Compose reset command for the local demo environment. Add an integration test proving that a clean reset followed by initialization and import recreates the same validated row counts and relationships from the pinned source revision.

## Phase 3: Governed Read-Only Access

- [X] **T007 [P] [US2]** Write failing allowed-query, relationship-query, and prohibited-field/entity tests in `tests/integration/test_graphjin_queries.py`, then configure PostgreSQL connectivity, source discovery, table relationships, explicit entity and field allowlists, result limits, and database-query timeout in `graphjin/config/dev.yml` and `graphjin/config/policies.yml`.

- [X] **T008 [P] [US2]** Write failing database-effect tests in `tests/security/test_read_only_access.py`, then grant the GraphJin runtime only the PostgreSQL read-only role. Verify that SELECT operations succeed while INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER, and DROP fail with zero database changes.

- [X] **T009 [US2]** Add `tests/integration/test_foundation_smoke.py` covering the complete path: start PostgreSQL, wait for health, initialize database, import the pinned dataset, start GraphJin, execute one authorized relationship query, and verify one unauthorized query is rejected.

## Phase 4: Validation and Closure

- [X] **T010** Run all database service, initialization, import, GraphJin, and read-only gates. Document prerequisites, startup, health checks, database creation, reset procedure, dataset provenance, schema, roles, GraphJin configuration, and failure rules in `specs/001-governed-itsm-data-foundation/quickstart.md` and `README.md`.

- [ ] **T011 MANUAL GATE** Human reviewer starts the environment from a clean state, verifies PostgreSQL health and database creation, reviews the import manifest and license attribution, checks schema relationships and row counts, executes an authorized GraphJin query, and confirms rejected write operations. The implementation agent MUST NOT tick this task.

## Dependencies and Execution Order

1. T001 and T002 may run in parallel.
2. T003 depends on T002.
3. T004 depends on T003.
4. T005 depends on T001 and T004.
5. T006 depends on T005.
6. T007 and T008 depend on T004-T005 and may run in parallel.
7. T009 depends on T006-T008.
8. T010 depends on T009.
9. T011 depends on T010 and is human-only.

## Validation Gates

```bash
pytest -q tests/integration/test_postgres_service.py
pytest -q tests/integration/test_database_initialization.py
pytest -q tests/integration/test_database_import.py
pytest -q tests/integration/test_graphjin_queries.py tests/security/test_read_only_access.py
pytest -q tests/integration/test_foundation_smoke.py
```

## Validation Checklist

- [ ] PostgreSQL image version is pinned.
- [ ] PostgreSQL health check succeeds before initialization begins.
- [ ] The application database is created explicitly and accepts connections.
- [ ] Schema initialization is idempotent.
- [ ] Dataset source, commit, license, attribution, and checksums are recorded.
- [ ] Import validation is atomic and reproducible.
- [ ] Clean reset plus reimport produces identical validated row counts.
- [ ] GraphJin uses only the read-only PostgreSQL role.
- [ ] Authorized reads succeed and all tested write/DDL operations fail with zero changes.
- [ ] T011 remains unchecked until human review.

## MANUAL GATE 3: Task Review

- **Approved with explicit PostgreSQL service, database creation, schema initialization, import, reset, and smoke-test tasks**
