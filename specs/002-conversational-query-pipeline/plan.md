# Implementation Plan: Conversational Query Pipeline

**Branch**: `[002-conversational-query-pipeline]`  
**Date**: 2026-10-09  
**Spec**: [spec.md](spec.md)

## Summary

Build a FastAPI and DSPy pipeline that converts natural-language ITSM questions into typed GraphQL or governed tool requests, executes them through the approved GraphJin foundation, and produces evidence-backed answers with sanitized traces.

## Technical Context

**Language/Version**: Python 3.12.x  
**Primary Dependencies**: DSPy, FastAPI, Pydantic, Uvicorn, HTTP client, pytest  
**LLM Runtime**: Local llama.cpp OpenAI-compatible endpoint  
**LLM Base URL**: `http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1`  
**Requested Model Artifact**: `openai/models\Qwen3.8-27B-UD-Q4_K_M.gguf`  
**Model Identity**: Discover exact API model ID using `GET /v1/models`, then pin it  
**Data Access**: GraphJin surface delivered by spec 001  
**Constraints**: No arbitrary SQL tool; no provider or model fallback; temperature 0 for measured runs; cache disabled for measured runs

## Constitution Check

- Repository constitution status is not yet verified.
- **MANUAL GATE**: Validate this plan and confirm spec 001 is complete.

## Architecture

```text
User question
    |
FastAPI request schema
    |
DSPy classifier + typed query planner
    |
Deterministic structured-request validator
    |
GraphJin GraphQL/MCP request
    |
Structured data result
    |
DSPy grounded-answer generator
    |
Answer/refusal + sanitized trace + latency
```

## Local Model Configuration

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1
LLM_MODEL=<EXACT_ID_FROM_/v1/models>
LLM_API_KEY=local-not-required
LLM_TEMPERATURE=0
LLM_CACHE=false
```

Preflight verifies `/v1/models`, one chat completion, one typed DSPy prediction, and the exact model ID. Failure stops implementation; no fallback is allowed.

## Key Decisions

1. **Use DSPy typed signatures for classification, planning, and answer generation**.  
   **Rejected alternative**: One untyped prompt producing executable text.

2. **Generate GraphQL or governed tool requests, not free-form SQL**.  
   **Rejected alternative**: Direct model-generated SQL.

3. **Use the pinned local Qwen model through llama.cpp for all model-dependent stages**.  
   **Rejected alternative**: Separate models or automatic hosted fallback.

4. **Validate structured requests deterministically before GraphJin execution**.  
   **Rejected alternative**: Trusting model output directly.

5. **Generate answers only from structured execution evidence**.  
   **Rejected alternative**: Answering from parametric knowledge.

6. **Return stable clarification, unsupported, and dependency error categories**.  
   **Rejected alternative**: Generic free-text errors.

## Project Structure

```text
app/
├── main.py
├── api/{routes.py,schemas.py}
├── ai/{signatures.py,query_program.py,answer_program.py,llm.py}
├── data/{graphjin_client.py,result_normalizer.py}
└── observability/trace.py
tests/{unit,contract,integration}/
artifacts/llm-preflight.json
.env.example
```

## Phases

1. Model preflight and typed contracts.
2. DSPy classification and query planning with deterministic validation.
3. GraphJin execution, result normalization, and grounded answers.
4. Sanitized trace, ambiguity handling, stable errors, and latency recording.
5. Unit, contract, and integration validation.

## Validation Gates

```bash
pytest -q tests/unit tests/contract
pytest -q tests/integration/test_conversational_flow.py
```

## Failure Rules

- Stop if the exact model cannot be verified.
- Do not fall back to another model or provider.
- Do not bypass GraphJin or fabricate an answer after dependency failure.

## MANUAL GATE 2: Plan Review

- **Approved**
