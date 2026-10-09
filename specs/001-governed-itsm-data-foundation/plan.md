# Implementation Plan: Governed ITSM Data Foundation

**Branch**: `[001-governed-itsm-data-foundation]`  
**Date**: 2026-10-09  
**Spec**: [spec.md](spec.md)

## Summary

Create a reproducible PostgreSQL data foundation from a pinned synthetic ITSM dataset and expose it only through a read-only GraphJin query surface with explicit policies, limits, provenance, and integration tests.

## Technical Context

**Language/Version**: Python 3.12.x, SQL, GraphJin v3  
**Primary Dependencies**: PostgreSQL, GraphJin, psycopg, pytest, Docker Compose  
**Dataset Source**: `https://github.com/drapertoby/itsm-ticket-dataset`  
**Storage**: PostgreSQL, immutable raw CSV files, JSON import manifest  
**Testing**: pytest integration and security tests  
**Target Platform**: Linux-compatible local Docker environment  
**Constraints**: Synthetic data only; pinned Git commit; MIT license verification; read-only access; no silent source substitution

## Constitution Check

- Repository constitution status is not yet verified.
- **MANUAL GATE**: Validate this plan against the repository constitution before implementation.

## Architecture

```text
Pinned Git commit
    |
License + SHA-256 verification
    |
Immutable merchants.csv / agents.csv / tickets.csv
    |
Pinned PostgreSQL container + health check
    |
Database creation and idempotent schema initialization
    |
Validated and atomic dataset import
    |
Read-only PostgreSQL role
    |
GraphJin policy-controlled GraphQL/MCP surface
```

## Key Decisions

1. **Use the public synthetic ITSM dataset at a pinned commit** for realistic relational structure without personal data.  
   **Rejected alternative**: Locally generated records, because they reduce realism and reproducibility.

2. **Run a pinned PostgreSQL service with persistent storage and health checks** and create the application database explicitly.  
   **Rejected alternative**: Assuming an existing manually configured database.

3. **Preserve raw inputs and generate an import manifest** containing commit SHA, license, attribution, checksums, row counts, and validation outcomes.  
   **Rejected alternative**: Copying mutable CSVs directly into initialization.

4. **Normalize into merchants, agents, and tickets tables** with explicit primary and foreign keys.  
   **Rejected alternative**: One denormalized table.

5. **Make database initialization and import reproducible and idempotent** and provide a clean reset path.  
   **Rejected alternative**: One-time manual setup.

6. **Enforce read-only access in both GraphJin and PostgreSQL**.  
   **Rejected alternative**: Relying on GraphJin policy alone.

7. **Fail closed** when source revision, license, checksums, required fields, relationships, database initialization, or health checks fail.  
   **Rejected alternative**: Partial import or silent repair.

## Project Structure

```text
compose.yml
.env.example
database/
├── bootstrap.sql
├── schema.sql
└── roles.sql
scripts/
├── initialize_database.py
├── import_dataset.py
└── reset_database.py
data/raw/
graphjin/config/
├── dev.yml
└── policies.yml
tests/integration/
├── test_postgres_service.py
├── test_database_initialization.py
├── test_database_import.py
├── test_graphjin_queries.py
└── test_foundation_smoke.py
tests/security/test_read_only_access.py
artifacts/import-manifest.json
```

## Phases

1. **Source and service preflight**: Verify dataset source and configure the pinned PostgreSQL service.
2. **Database creation**: Create the application database, schema, tables, indexes, owner role, and read-only role.
3. **Import and reset**: Validate and atomically import the pinned data; prove reproducible reset and reimport.
4. **Governed access**: Configure GraphJin relationships, allowlists, limits, timeouts, and read-only credentials.
5. **Validation**: Run service, initialization, import, policy, write-rejection, and full smoke gates.

## Validation Gates

```bash
pytest -q tests/integration/test_postgres_service.py
pytest -q tests/integration/test_database_initialization.py
pytest -q tests/integration/test_database_import.py
pytest -q tests/integration/test_graphjin_queries.py tests/security/test_read_only_access.py
pytest -q tests/integration/test_foundation_smoke.py
```

## Failure Rules

- Stop if source revision, license, PostgreSQL health, database initialization, or import validation fails.
- Do not substitute another dataset or generate replacement records.
- Do not expose a writable database credential to downstream components.

## MANUAL GATE 2: Plan Review

- **Approved**
