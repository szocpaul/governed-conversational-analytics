# Tasks: Secure Conversational Analytics Demo

**Input**: Approved artifacts from `/specs/[NNN-conversational-analytics-demo]/`  
**Tests**: Tests MUST be written first and observed failing before implementation.

> **MANUAL GATE**: Replace `NNN` with the verified repository sequence number.

## Phase 1: Preflight and Setup

- [ ] **T001 [P]** Create the project structure and pin dependencies in `requirements.lock`, `compose.yml`, `Dockerfile`, and `.env.example`. Configure `LLM_BASE_URL=http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1`, `LLM_PROVIDER=openai-compatible`, `LLM_TEMPERATURE=0`, and `LLM_CACHE=false`. Query `/v1/models`, record the exact API model ID corresponding to `openai/models\Qwen3.8-27B-UD-Q4_K_M.gguf`, run chat-completions, DSPy, and GraphJin smoke tests, and write non-secret metadata to `artifacts/llm-preflight.json`. Stop and report if any check fails; do not use another model or provider.

- [ ] **T002 [P]** Use the MIT-licensed dataset at `https://github.com/drapertoby/itsm-ticket-dataset`. Pin its commit SHA, preserve license/attribution, record SHA-256 checksums, keep raw files unchanged, and implement `scripts/import_dataset.py` plus `database/schema.sql`. Add import and read-only tests verifying row counts, required fields, foreign keys, successful reads, and rejected INSERT, UPDATE, DELETE, and DDL operations.

- [ ] **T003 [P]** Define structured query, answer/refusal, latency, and sanitized-trace contracts in `contracts/query-request.schema.json`, `contracts/api.openapi.yaml`, and `app/api/schemas.py`; add `tests/contract/test_api_contract.py`.

## Phase 2: Governed Data Access

- [ ] **T004 [US2]** Write failing GraphJin policy/integration tests, then configure `graphjin/config/dev.yml` and `graphjin/config/policies.yml` for the pinned local OpenAI-compatible endpoint/model where model-assisted GraphJin features are enabled, plus read-only operations, entity/field allowlists, limits, timeout, and roles. Verify no direct arbitrary-SQL bypass exists.

## Phase 3: Query Flow and Security

- [ ] **T005 [P] [US1]** Write failing query-program tests, then implement DSPy signatures and typed query planning in `app/ai/signatures.py` and `app/ai/query_program.py` using only the configured local endpoint and exact API model ID.

- [ ] **T006 [P] [US2]** Write failing prompt-injection, unauthorized-access, timeout, and redaction tests, then implement deterministic validation, injection signaling, refusal categories, and redaction in `app/security/`. Injection classification MUST NOT be the security boundary.

- [ ] **T007 [US1]** Write failing end-to-end tests, then implement GraphJin execution, result normalization, DSPy grounded-answer generation, sanitized tracing, and FastAPI orchestration. Never fabricate an answer or fall back to another model.

## Phase 4: Evaluation and Regression

- [ ] **T008 [P] [US3]** Create versioned development and held-out evaluation sets with at least 20 evaluation cases, including at least 5 security/unauthorized cases.

- [ ] **T009 [US3]** Write failing metric and regression-gate tests, then implement deterministic validity, execution accuracy, security effect, disclosure, false-refusal, and observational latency metrics. Artifacts MUST record endpoint class, exact API model ID, requested GGUF artifact, llama.cpp build/version when available, parameters, and cache state.

- [ ] **T010 [US3]** With `temperature=0` and cache disabled, measure a representative sample two or three times, record noise, then save `artifacts/baseline.json`. Stop if the exact pinned model cannot be verified.

- [ ] **T011 [US3]** Optimize DSPy using only the development split, rerun held-out evaluation with the same pinned model/configuration, save `artifacts/current.json`, and fail comparison for P1 quality/security regression. Latency remains observational.

## Phase 5: Interface and Validation

- [ ] **T012 [US4]** Implement the tested FastAPI-served UI with answer/refusal, observational latency, and sanitized trace. Do not expose the private endpoint or internal prompts in the UI.

- [ ] **T013** Run `pytest -q`, uncached evaluation, and baseline comparison. Document local endpoint configuration, exact API model ID discovery, model artifact, GraphJin/DSPy setup, dataset attribution, and all validation evidence in `README.md` and `quickstart.md`.

- [ ] **T014 MANUAL GATE** Human reviewer validates the demo, model identity, refusal behavior, trace redaction, baseline/current artifacts, and observational latency. The implementation agent MUST NOT tick this checkbox.

## Dependencies

1. T001-T003 may run in parallel, but no model-dependent task may start until T001 preflight passes.
2. T004 depends on T001-T003.
3. T005-T006 depend on T004 and may run in parallel.
4. T007 depends on T005-T006.
5. T008 may start after T003; T009 depends on T007-T008.
6. T010 depends on T009; T011 depends on T010.
7. T012 depends on T007; T013 depends on T004-T012; T014 depends on T013.

## Validation Checklist

- [ ] Exact model ID from `/v1/models` is recorded and used by DSPy and GraphJin.
- [ ] Requested artifact is recorded as `openai/models\Qwen3.8-27B-UD-Q4_K_M.gguf`.
- [ ] No cloud or alternate-model fallback exists.
- [ ] Cache is disabled for measured runs and temperature is zero.
- [ ] GraphJin and PostgreSQL enforce read-only access.
- [ ] Dataset revision, license, attribution, and checksums are recorded.
- [ ] Latency is observational only.
- [ ] T014 remains unchecked until human review.

## MANUAL GATE 4: Task Review

- **Approved with the local llama.cpp/Qwen configuration correction**
