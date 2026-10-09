# Governed Conversational Analytics

A governed conversational analytics project built with Spec Kit. Natural-language
questions are answered over a reproducible, read-only, policy-controlled ITSM
dataset — never through arbitrary SQL or unrestricted credentials.

## Features

1. **[001-governed-itsm-data-foundation](specs/001-governed-itsm-data-foundation/)** —
   reproducible PostgreSQL foundation from a pinned synthetic ITSM dataset
   (MIT-licensed, commit-pinned, SHA-256 verified) behind a read-only GraphJin
   GraphQL surface with explicit entity/field allowlists, result limits, and a
   database-query timeout. See its
   [quickstart](specs/001-governed-itsm-data-foundation/quickstart.md).
2. `002-conversational-query-pipeline` — planned (DSPy planning over the governed surface).
3. `003-security-hardening` — planned.
4. `004-evaluation-and-demo` — planned.

## Quick start (feature 001)

```bash
cp .env.example .env
sudo docker compose up -d --wait postgres
python3 scripts/initialize_database.py
python3 scripts/import_dataset.py
sudo docker compose up -d graphjin
pytest -q
```

Dataset: [Synthetic ITSM Helpdesk Ticket Dataset](https://github.com/drapertoby/itsm-ticket-dataset)
by drapertoby, MIT License, pinned to commit `cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`.

## Repository layout

```text
compose.yml                 # pinned PostgreSQL + GraphJin services
.env.example                # placeholder configuration (no real secrets)
database/                   # bootstrap.sql, schema.sql, roles.sql
scripts/                    # initialize_database.py, import_dataset.py, reset_database.py
data/raw/                   # immutable pinned source CSVs + LICENSE
graphjin/config/            # dev.yml + policies.yml (governed access policy)
tests/                      # integration and security test gates
artifacts/import-manifest.json  # provenance, checksums, import results
specs/                      # approved Spec Kit artifacts per feature
```
