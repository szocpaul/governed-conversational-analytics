# Implementation Plan: Secure Conversational Analytics Demo

**Branch**: `[NNN-conversational-analytics-demo]`  
**Date**: 2026-10-09  
**Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/[NNN-conversational-analytics-demo]/spec.md`

> **MANUAL GATE**: Replace `NNN` with the next sequence number from the target repository before committing these artifacts.

## Summary

Build a read-only conversational analytics demo that converts natural-language questions into structured requests, executes them through a governed backend, and returns evidence-backed answers with a sanitized trace.

DSPy will handle question interpretation, typed query planning, grounded answer generation, optimization, and evaluation. GraphJin will provide the governed GraphQL/MCP data-access layer and backend policy enforcement. Both DSPy and GraphJin agent/model integrations will use the same local OpenAI-compatible llama.cpp endpoint and pinned Qwen model defined below. PostgreSQL will be populated from a pinned public synthetic ITSM dataset. FastAPI and a minimal browser interface will expose the flow.

## Technical Context

**Language/Version**: Python 3.12.x; GraphJin as a separately pinned service/container  
**Primary Dependencies**: DSPy, FastAPI, Pydantic, Uvicorn, PostgreSQL driver, GraphJin v3, Docker Compose  
**LLM Runtime**: Local llama.cpp server exposing an OpenAI-compatible API  
**LLM Base URL**: `http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1`  
**Requested Model Artifact**: `openai/models\Qwen3.8-27B-UD-Q4_K_M.gguf`  
**Model Identity Rule**: Before implementation, query `GET /v1/models` and record the exact model identifier returned by the server. Use that exact identifier in DSPy and GraphJin configuration. If it differs from the requested artifact path, record both the artifact path and API model ID.  
**Storage**: PostgreSQL populated from the pinned public synthetic ITSM dataset; JSON evaluation, baseline, and run artifacts  
**Testing**: pytest unit, contract, integration, security, and evaluation-gate tests  
**Target Platform**: Linux-compatible local environment with Docker Engine and Docker Compose; network access to the private llama.cpp endpoint is required  
**Performance Goals**: Record per-request latency and report median, p90, and maximum. Latency is observational and has no pass/fail threshold in this demo.  
**Constraints**: Read-only data access; zero prohibited operations; zero unauthorized disclosure; uncached measurement runs; no fallback to another model or hosted API

## Local LLM Configuration

The implementation MUST expose configuration through environment variables and MUST NOT hard-code the endpoint in application code:

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1
LLM_MODEL=<EXACT_ID_RETURNED_BY_GET_/v1/models>
LLM_API_KEY=local-not-required
LLM_TEMPERATURE=0
LLM_CACHE=false
```

`LLM_API_KEY` is a non-secret compatibility placeholder only if the OpenAI-compatible client requires a value. It MUST NOT be treated as a real credential.

### Required LLM Preflight

Before dataset work, optimization, or baseline measurement:

1. Resolve the endpoint hostname from the implementation environment.
2. Call `GET http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1/models`.
3. Verify that the expected Qwen model is loaded and record the exact API model ID.
4. Run one deterministic chat-completions smoke request against the exact model ID.
5. Verify that DSPy can complete one typed prediction through the endpoint.
6. Verify that GraphJin can use the same endpoint/model for any enabled server-side agent or model-assisted operation.
7. Save non-secret preflight metadata to `artifacts/llm-preflight.json`.

If the endpoint is unreachable, the model is absent, the API is incompatible, or either DSPy or GraphJin cannot use it, implementation MUST stop and report. It MUST NOT switch to OpenAI, Azure OpenAI, Anthropic, or another local model.

## Version Pinning

Pin Python, DSPy, GraphJin, PostgreSQL, FastAPI, Pydantic, Uvicorn, pytest, database driver, model artifact name, exact API model ID, llama.cpp server/build version when available, generation parameters, prompt, policy, schema, source-dataset commit/checksums, and evaluation-dataset version before recording the baseline.

A model artifact, API model ID, llama.cpp build, GraphJin, principal dependency, prompt, policy, schema, source dataset, or evaluation dataset change requires a new baseline.

## Constitution Check

- **Repository constitution status**: Not verified.
- **MANUAL GATE**: Check the target repository for a Spec Kit constitution and validate this plan against it.

## Architecture

```text
Browser UI
    |
FastAPI endpoint
    |
DSPy via local llama.cpp OpenAI-compatible API
    |
Typed query planner and deterministic validator
    |
GraphJin governed GraphQL/MCP layer
    |          \
    |           +--> same local llama.cpp endpoint if GraphJin agent/model features are enabled
    |
Read-only PostgreSQL role
    |
Imported synthetic ITSM data
    |
Grounded answer + sanitized trace + observational latency
```

```text
Pinned dataset commit
    |
License and SHA-256 verification
    |
Immutable raw CSV files
    |
Validation and normalization
    |
PostgreSQL application tables
```

## Key Decisions

1. **GraphJin is the governed data-access boundary**. The model receives no unrestricted database credentials and cannot execute arbitrary SQL.  
   **Rejected alternative**: Direct model-generated SQL execution.

2. **DSPy provides typed generative programs and evaluation-aware optimization**.  
   **Rejected alternative**: A single handwritten prompt without structured evaluation.

3. **Use one pinned local model endpoint for DSPy and GraphJin**: `http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1`, serving the requested `openai/models\Qwen3.8-27B-UD-Q4_K_M.gguf` artifact. The exact API model ID is discovered through `/v1/models` and then pinned.  
   **Rejected alternative**: Different models per component or an automatic cloud fallback, because that would weaken reproducibility and make evaluation attribution ambiguous.

4. **No model fallback**. Endpoint or model failure stops the run and is reported.  
   **Rejected alternative**: Silent fallback to another model/provider.

5. **Defense in depth defines security**. Prompt-injection classification is a signal; GraphJin policy and a read-only PostgreSQL role are the security boundary.

6. **Deterministic evaluation is used wherever ground truth exists**. LLM-as-a-judge is optional and supplementary.

7. **Latency is observational in the first demo**. No arbitrary latency quality threshold is introduced.

8. **Use the MIT-licensed Synthetic ITSM Helpdesk Ticket Dataset** from `https://github.com/drapertoby/itsm-ticket-dataset`. Pin an exact commit SHA, preserve license/attribution, verify checksums, and keep raw files immutable.

9. **Serve a minimal UI from FastAPI** to avoid a separate frontend toolchain.

## Dataset Import and Failure Rule

Import and normalize `merchants.csv`, `agents.csv`, and `tickets.csv`. Record source URL, commit SHA, license, attribution, SHA-256 checksums, row counts, required-field validation, and foreign-key validation.

If the pinned revision or license cannot be verified, stop and report. Do not substitute another dataset or generate replacement records.

## Security Design

- GraphJin is the only application path to analytical data.
- GraphJin uses a read-only PostgreSQL role.
- Allowed entities, fields, relationships, operations, roles, and result limits are explicit.
- Structured requests are schema-validated before execution.
- Prompt-injection detection is not the security boundary.
- Security tests verify actual effects and disclosure.
- Traces redact credentials, prompts, secrets, and protected data.
- The local LLM endpoint remains configuration data and is not exposed in the user-facing trace.

## Evaluation and Measurement Design

- Separate development/optimization and held-out evaluation sets.
- Deterministic metrics: request validity, executable-query rate, normalized execution accuracy, security blocking, unauthorized disclosure, false refusals, and latency.
- Baseline and comparison runs use `LLM_CACHE=false` and `temperature=0`.
- Every result artifact records the exact API model ID and requested model artifact.
- LLM-as-a-judge cannot override correctness or security failures.
- Latency is reported per request plus median, p90, and maximum, but is excluded from pass/fail.

### Required Gates

```bash
pytest -q
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

## Error Handling

- Local LLM endpoint unavailable or model missing: stop and report.
- DSPy or GraphJin cannot use the configured OpenAI-compatible API: stop and report.
- Invalid structured output: stable validation error.
- GraphJin unavailable: dependency-unavailable error.
- Dataset source/license unverifiable: stop and report.
- Database timeout: cancel and return database-timeout.
- Overall safety timeout: terminate request; do not treat it as a latency target.
- Never simulate model, database, or evaluation results.

## Project Structure

```text
specs/[NNN-conversational-analytics-demo]/
├── spec.md
├── plan.md
└── tasks.md

app/{api,ai,security,data,observability,web}/
graphjin/config/
database/
scripts/import_dataset.py
data/raw/
evaluation/
artifacts/
tests/{unit,contract,integration,security,evaluation}/
compose.yml
Dockerfile
requirements.lock
.env.example
README.md
```

## Implementation Phases

1. Preflight constitution, repository sequence, local LLM endpoint/model, GraphJin, PostgreSQL, and dataset source/license.
2. Pin dependencies, model identity, model parameters, dataset revision, and checksums.
3. Import dataset and define contracts and GraphJin policies.
4. Implement DSPy query flow and grounded answers using the pinned local model.
5. Enforce security controls and prompt-injection tests.
6. Build uncached evaluation, baseline, regression comparison, and DSPy optimization.
7. Add the minimal UI and complete validation.

## MANUAL GATE 3: Plan Review

- **Approved with the local llama.cpp/Qwen configuration correction**
