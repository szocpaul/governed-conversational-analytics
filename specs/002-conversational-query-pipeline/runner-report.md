# Runner Report: Feature 002 — Conversational Query Pipeline

**Date**: 2026-10-09
**Scope**: automatable tasks T001–T008. T009 is a MANUAL GATE and is left
unchecked for the human reviewer.

## 1. Completed task IDs

- **T001** — Model preflight: `.env.example` LLM config, pinned local model
  client (`app/ai/llm.py`), preflight runner (`app/ai/preflight.py`), verified
  artifact `artifacts/llm-preflight.json`.
- **T002** — Typed API/request schemas (`app/api/schemas.py`) and DSPy
  signatures (`app/ai/signatures.py`); contract tests
  (`tests/contract/test_api_contract.py`).
- **T003** — DSPy `QueryProgram` (classify + plan) with deterministic JSON
  parsing (`app/ai/query_program.py`); unit tests
  (`tests/unit/test_query_program.py`).
- **T004** — Deterministic validator (`app/security/validator.py`) and stable
  sanitized error categories (`app/security/errors.py`); unit tests
  (`tests/unit/test_validator.py`).
- **T005** — Governed GraphJin client (`app/data/graphjin_client.py`) and
  result normalizer (`app/data/result_normalizer.py`); integration tests
  (`tests/integration/test_conversational_flow.py`).
- **T006** — Grounded `AnswerProgram` with deterministic grounding check
  (`app/ai/answer_program.py`) and sanitized `Trace`
  (`app/observability/trace.py`); unit tests
  (`tests/unit/test_answer_program.py`).
- **T007** — FastAPI orchestration (`app/api/routes.py`, `app/main.py`) with
  stable categories, grounding refusal, and no-fallback dependency errors;
  API tests (`tests/unit/test_api_routes.py`).
- **T008** — Validation gates run; docs in `quickstart.md` and `README.md`;
  pinned `requirements.txt`.

## 2. Incomplete / blocked task IDs

- **T009 MANUAL GATE** — intentionally not started. Awaiting human reviewer.

## 3. Files changed

- `.env.example` (added LLM + GraphJin config placeholders)
- `requirements.txt` (new, pinned)
- `README.md` (feature 002 section + quickstart)
- `artifacts/llm-preflight.json` (new, non-secret preflight metadata)
- `app/__init__.py`, `app/main.py`
- `app/api/__init__.py`, `app/api/schemas.py`, `app/api/routes.py`
- `app/ai/__init__.py`, `app/ai/llm.py`, `app/ai/preflight.py`,
  `app/ai/signatures.py`, `app/ai/query_program.py`, `app/ai/answer_program.py`
- `app/data/__init__.py`, `app/data/graphjin_client.py`,
  `app/data/result_normalizer.py`
- `app/security/__init__.py`, `app/security/errors.py`,
  `app/security/validator.py`
- `app/observability/__init__.py`, `app/observability/trace.py`
- `tests/__init__.py`, `tests/unit/__init__.py`, `tests/contract/__init__.py`,
  `tests/integration/__init__.py`
- `tests/contract/test_api_contract.py`
- `tests/unit/test_query_program.py`, `tests/unit/test_validator.py`,
  `tests/unit/test_answer_program.py`, `tests/unit/test_api_routes.py`
- `tests/integration/test_conversational_flow.py`
- `specs/002-conversational-query-pipeline/quickstart.md`
- `specs/002-conversational-query-pipeline/tasks.md` (T001–T008 marked [X])

No spec 001 files were modified. No work on specs 003/004.

## 4. Commits created

- `cf112ba` T001: LLM preflight
- `70ad358` T002: typed schemas + DSPy signatures
- `6ef1fce` T003: DSPy QueryProgram
- `940513f` T004: validator + error categories
- `f270f9a` T005: GraphJin client + normalizer
- `b8bfae2` T006: grounded AnswerProgram + Trace
- `13902e6` T007: FastAPI orchestration
- `c13a060` T003/T006 robustness refinements (planner shape tolerance,
  explicit PlanQuery example, list-ordinal scrub in grounding)
- `9a7f786` T008: requirements + README + quickstart
- `8f2743b` T001–T008 complete; T009 manual gate left

## 5. Pinned dependency versions

- dspy 3.2.1
- fastapi 0.143.0
- uvicorn[standard] 0.45.0
- pydantic 2.12.5
- httpx 0.28.1
- pytest 9.0.3
- Python 3.12.3 (system)

## 6. Dataset

Unchanged from feature 001. Source
`https://github.com/drapertoby/itsm-ticket-dataset`, MIT license, pinned commit
`cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`; checksums in
`artifacts/import-manifest.json` (feature 001).

## 7. Model identity

- Exact API model ID: `models\Qwen3.8-27B-UD-Q4_K_M.gguf`
  (single backslash in the actual ID), verified via `GET /v1/models`.
- Provider: `openai-compatible` (local llama.cpp). No fallback configured.
- llama.cpp version: not separately reported by `/v1/models`; the endpoint
  reports `owned_by: llamacpp`, `n_params: 27320697856`, `ftype: Q4_K -
  Medium`, `n_ctx: 65536`. Recorded in `artifacts/llm-preflight.json`.
- Temperature 0, cache false for measured runs.

## 8. Validation commands and results

```bash
pytest -q tests/unit tests/contract            # 45 passed
pytest -q tests/integration/test_conversational_flow.py  # 8 passed
pytest -q                                      # 93 passed (full suite)
```

All gates pass. TDD followed: every test file was observed failing before its
implementation.

## 9. End-to-end proof with the pinned model

Real (non-stubbed) runs through the full flow with the pinned local model:

- "How many P1 tickets are there?" -> supported -> governed count query ->
  evidence `{count: 112}` -> answer "There are 112 P1 tickets." (grounded).
- "Show me 3 tickets with their merchant names" -> supported -> relationship
  list query -> grounded answer with real merchant names (grounded).
- "What is the average resolution time for P2 tickets?" -> supported ->
  avg query -> grounded answer (~15.15 hours).
- "Tell me about stuff" -> unsupported -> refusal, no query executed.

## 10. Security-effect and disclosure results

- No arbitrary SQL tool is exposed to the model; the planner emits only a
  typed `StructuredQueryRequest` JSON, validated deterministically against the
  governed allowlist before execution.
- The only database path is GraphJin (read-only). Integration test
  `test_read_only_surface_rejects_mutation` confirms mutations are rejected.
- Traces and error messages are sanitized: private endpoint URL, bearer
  tokens, and IP:port pairs are redacted (unit-tested). The private endpoint
  appears only as a placeholder in `.env.example` and as non-secret metadata
  in `artifacts/llm-preflight.json`.
- Ungrounded answers (fabricated values absent from evidence) are refused and
  never returned as fact (unit + API tested).

## 11. Latency (observational only)

From preflight (`artifacts/llm-preflight.json`):
- chat completion: ~466 ms
- typed DSPy prediction: ~1254 ms

Per-request `latency_ms` is returned on every API response. Aggregate
median/p90/max are not computed here (out of scope for feature 002; feature
004 owns evaluation metrics). Latency is observational and not a pass/fail
gate.

## 12. Known limitations

- GraphJin group-by is not enabled in the current governed config, so the
  planner targets filtered lists, filtered aggregates (count/sum/avg/min/max),
  and relationship traversal — not grouped breakdowns.
- The deterministic grounding check is heuristic (numbers + proper-noun
  phrases); it scrubs list-ordinal markers but may be conservative on free
  text. It errs toward refusal, never toward fabrication.
- Unit/API tests stub the LLM for speed/determinism; the real-model path is
  covered by the preflight and the manual end-to-end smoke above. A full
  held-out evaluation is feature 004 scope.

## 13. Outstanding manual gates

- **T009 MANUAL GATE**: human reviewer runs supported, relationship,
  ambiguous, empty-result, and endpoint-failure scenarios and approves the
  traces. Not ticked by the implementation agent.
