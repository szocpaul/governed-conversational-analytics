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
2. **[002-conversational-query-pipeline](specs/002-conversational-query-pipeline/)** — FastAPI + DSPy pipeline that turns natural-language questions into typed, validated GraphQL requests executed only through the governed GraphJin surface, returning evidence-backed answers with sanitized traces and latency. Uses the pinned local llama.cpp model with no fallback. See its [quickstart](specs/002-conversational-query-pipeline/quickstart.md).
3. **[003-security-hardening](specs/003-security-hardening/)** — adversarial tests and deterministic controls proving that prompt manipulation, unsafe structured requests, prohibited fields, excessive queries, and trace/error paths produce no unauthorized effects or disclosures. See the security section below.
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

## Quick start (feature 002)

```bash
cp .env.example .env          # set LLM_BASE_URL and LLM_MODEL to pinned values
python3 -m app.ai.preflight   # verify the pinned local model (no fallback)
uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -s -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "How many P1 tickets are there?"}'
```

## Security hardening (feature 003)

Feature 003 proves that malicious, manipulated, or unauthorized conversational
requests cannot bypass backend access policy, modify data, disclose prohibited
values, or expose sensitive internal information. Security is judged by
**backend effects and disclosure**, never by refusal wording (FR-001, FR-005).

### Threat model

| Threat | Boundary that stops it |
|--------|------------------------|
| Direct prompt injection ("ignore instructions, DROP TABLE") | Deterministic validator + GraphJin read-only policy + PostgreSQL read-only role |
| Indirect injection (instructions hidden in data) | Same deterministic controls; the model never gets an arbitrary-SQL tool |
| Obfuscated / multilingual / mixed injection | Same deterministic controls (defense in depth below the model) |
| Unsafe structured request submitted below the model | Type-level allowlist + deterministic validator re-check |
| Unauthorized entity/field/row scope | GraphJin `default_block: true` + explicit allowlists + PostgreSQL role |
| Excessive query (resource exhaustion) | Independent DB-query timeout, request safety timeout, and result-size cap |
| Trace/error disclosure of secrets or endpoint | Deterministic `redact()` on every user-facing string |

### Deterministic boundaries (the actual security controls)

1. **Type-level allowlist** (`app/api/schemas.py`): entities, fields,
   relationships, operations, and limit range are enforced by Pydantic at
   construction time.
2. **Deterministic validator** (`app/security/validator.py`): re-checks every
   constraint on the typed request before any execution; pure function, no
   model, no I/O.
3. **GraphJin policy** (`graphjin/config/policies.yml`): `default_block: true`,
   explicit entity/field/relationship allowlists, `read_only: true`,
   `default_limit: 100`.
4. **PostgreSQL read-only role** (`itsm_readonly`): the runtime query path
   connects only with this role; INSERT/UPDATE/DELETE/TRUNCATE/CREATE/ALTER/
   DROP are denied and verified to leave zero changes.

### Independent limits (FR-004)

| Control | Value | Scope |
|---------|-------|-------|
| Database-query timeout | 5 s (`DB_QUERY_TIMEOUT_S`) | single GraphJin query |
| Request safety timeout | 120 s (`REQUEST_SAFETY_TIMEOUT_S`) | whole `/query` request |
| Maximum result size | 100 rows (`MAX_LIMIT`) | app type layer + GraphJin default |

### Injection classifier is telemetry, never authorization

`app/security/classifier.py` produces an `InjectionSignal` used only for trace
telemetry. It has **no** allow/deny/authorized semantics (FR-001). A flagged
question is still processed by the deterministic controls; an unflagged unsafe
request is still blocked. This is proven by
`tests/security/test_prompt_injection.py::test_classifier_not_authorization_boundary`.

### Test-only canaries

`evaluation/security_cases.json` seeds synthetic canary values
(`CANARY_SECRET_...`, `CANARY_PASSWORD_...`, `CANARY_TOKEN_...`,
`CANARY_PROMPT_FRAGMENT_...`) and the private endpoint string. Every trace,
error, and response is checked for zero disclosure of these values
(`tests/security/test_trace_redaction.py`). These are synthetic test values,
never real credentials.

### Security evaluation

```bash
python3 evaluation/run_security.py   # writes artifacts/security-results.json
pytest -q tests/security
pytest -q tests/integration/test_conversational_flow.py
```

`artifacts/security-results.json` records per-case effect, disclosure,
blocked-category, and false-refusal results plus aggregate metrics.

### Known exclusions

Out of scope per the approved spec: a dedicated ML attack classifier, a
complete red-team platform, enterprise SSO, SIEM integration, and production
incident response.

## Repository layout

```text
compose.yml                 # pinned PostgreSQL + GraphJin services
.env.example                # placeholder configuration (no real secrets)
database/                   # bootstrap.sql, schema.sql, roles.sql
scripts/                    # initialize_database.py, import_dataset.py, reset_database.py
data/raw/                   # immutable pinned source CSVs + LICENSE
graphjin/config/            # dev.yml + policies.yml (governed access policy)
app/                        # feature 002 pipeline (api, ai, data, security, observability)
tests/                      # unit, contract, integration and security test gates
artifacts/import-manifest.json  # provenance, checksums, import results
specs/                      # approved Spec Kit artifacts per feature
```
