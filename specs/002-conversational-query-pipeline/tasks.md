# Tasks: Conversational Query Pipeline

**Spec**: `specs/002-conversational-query-pipeline/spec.md`  
**Plan**: `specs/002-conversational-query-pipeline/plan.md`

## Phase 1: Model Preflight and Contracts

- [ ] **T001 [P]** Configure `.env.example` for the local OpenAI-compatible endpoint, call `/v1/models`, verify the requested Qwen artifact, run chat-completion and typed DSPy smoke tests, and save non-secret metadata to `artifacts/llm-preflight.json`. Stop without fallback if verification fails.
- [ ] **T002 [P] [US1]** Write failing API and structured-request contract tests in `tests/contract/test_api_contract.py`, then define typed question, request, answer/refusal, trace, and latency models in `app/api/schemas.py` and DSPy signatures in `app/ai/signatures.py`.

## Phase 2: Conversational Query Flow

- [ ] **T003 [P] [US1]** Write failing supported, relationship, time-filter, and empty-result tests in `tests/unit/test_query_program.py`, then implement DSPy classification and typed GraphQL/tool-request planning in `app/ai/query_program.py` using only the pinned local model.
- [ ] **T004 [P] [US2]** Write failing ambiguous, unsupported, malformed-output, and endpoint-failure tests, then implement deterministic request validation and stable error categories in `app/security/validator.py` and `app/security/errors.py`.
- [ ] **T005 [US1]** Write failing integration tests in `tests/integration/test_conversational_flow.py`, then implement GraphJin execution and normalized evidence handling in `app/data/graphjin_client.py` and `app/data/result_normalizer.py`.
- [ ] **T006 [US1] [US3]** Implement DSPy grounded-answer generation and sanitized execution tracing in `app/ai/answer_program.py` and `app/observability/trace.py`; prove that answers contain no factual value absent from execution evidence.
- [ ] **T007 [US1] [US2] [US3]** Implement FastAPI orchestration in `app/api/routes.py` and `app/main.py`, including clarification, refusal, dependency failure, latency, and no-model-fallback behavior.

## Phase 3: Validation and Closure

- [ ] **T008** Run all unit, contract, and integration gates; document model preflight, GraphJin dependency, configurations, supported question patterns, trace fields, and failure behavior in `quickstart.md` and `README.md`.
- [ ] **T009 MANUAL GATE** Human reviewer runs supported, relationship, ambiguous, empty-result, and endpoint-failure scenarios and approves the traces. The implementation agent MUST NOT tick this task.

## Dependencies

1. T001-T002 may run in parallel.
2. T003-T004 depend on T001-T002 and may run in parallel.
3. T005 depends on T003-T004 and completed spec 001.
4. T006 depends on T005.
5. T007 depends on T004-T006.
6. T008 depends on T007; T009 depends on T008.

## Validation Gates

```bash
pytest -q tests/unit tests/contract
pytest -q tests/integration/test_conversational_flow.py
```

## MANUAL GATE 3: Task Review

- **Approved**
