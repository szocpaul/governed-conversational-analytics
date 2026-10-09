# Tasks: Conversational Analytics Security Hardening

**Spec**: `specs/003-security-hardening/spec.md`  
**Plan**: `specs/003-security-hardening/plan.md`

## Phase 1: Threat Cases and Deterministic Evidence

- [x] **T001 [P] [US1]** Create versioned direct, indirect, obfuscated, multilingual, and mixed prompt-injection cases in `evaluation/security_cases.json`, including expected effects, disclosure expectations, and legitimate controls.
- [x] **T002 [P] [US3]** Seed test-only canary secrets, prohibited values, endpoint strings, and prompt fragments in fixtures, then write failing trace/error disclosure tests in `tests/security/test_trace_redaction.py`.

## Phase 2: Backend Security Controls

- [x] **T003 [P] [US1]** Write failing injection-effect tests in `tests/security/test_prompt_injection.py`, then implement injection signaling in `app/security/classifier.py` while ensuring it is not used as authorization.
- [x] **T004 [P] [US2]** Write failing direct unsafe-request and authorization tests in `tests/security/test_direct_unsafe_requests.py` and `tests/security/test_authorization.py`, then harden deterministic validation, GraphJin allowlists, and PostgreSQL read-only enforcement.
- [x] **T005 [P] [US2]** Write failing timeout and result-limit tests in `tests/security/test_limits_and_timeouts.py`, then enforce independent database timeout, request safety timeout, and maximum result size.
- [x] **T006 [US3]** Implement stable security/error categories and canary redaction in `app/security/redaction.py` and `app/security/errors.py`; ensure response, trace, and log outputs contain zero seeded secrets or prohibited values.

## Phase 3: Security Evaluation and Closure

- [x] **T007 [US1] [US2] [US3]** Run security cases plus legitimate analytical controls; write machine-readable effect, disclosure, blocked-category, and false-refusal results to `artifacts/security-results.json`.
- [x] **T008** Run full security and conversational-flow regression gates and document the threat model, deterministic boundaries, limits, canaries, and known exclusions in `README.md`.
- [ ] **T009 MANUAL GATE** Human reviewer inspects security effects, false refusals, and redacted responses/traces and approves or rejects the hardening. The implementation agent MUST NOT tick this task.

## Dependencies

1. T001-T002 may run in parallel.
2. T003-T005 depend on T001 and may run in parallel.
3. T006 depends on T002-T005.
4. T007 depends on T003-T006.
5. T008 depends on T007; T009 depends on T008.

## Validation Gates

```bash
pytest -q tests/security
pytest -q tests/integration/test_conversational_flow.py
```

## MANUAL GATE 3: Task Review

- **Approved**
