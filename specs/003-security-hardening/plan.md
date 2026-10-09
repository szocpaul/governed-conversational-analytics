# Implementation Plan: Conversational Analytics Security Hardening

**Branch**: `[003-security-hardening]`  
**Date**: 2026-10-09  
**Spec**: [spec.md](spec.md)

## Summary

Add adversarial tests and deterministic controls around the conversational pipeline to prove that prompt manipulation, unsafe structured requests, prohibited fields, excessive queries, and trace/error paths produce no unauthorized effects or disclosures.

## Technical Context

**Language/Version**: Python 3.12.x, SQL, GraphJin policy configuration  
**Primary Dependencies**: Approved specs 001 and 002, pytest, Pydantic  
**Testing**: Security, integration, and fault-injection tests  
**Constraints**: Security judged by effects and disclosure; classifier is not the security boundary; synthetic test secrets only

## Constitution Check

- Repository constitution status is not yet verified.
- **MANUAL GATE**: Validate this plan and confirm specs 001 and 002 are complete.

## Architecture

```text
Question or direct structured test request
    |
Injection signal / request classification
    |
Deterministic validator
    |
GraphJin policy and limits
    |
Read-only PostgreSQL role
    |
Sanitized response, error, and trace
```

## Key Decisions

1. **Test actual backend effects and disclosure**.  
   **Rejected alternative**: Scoring only refusal wording.

2. **Submit unsafe structured requests directly to lower layers** to prove controls survive model failure.  
   **Rejected alternative**: Testing only model-generated requests.

3. **Treat injection classification as telemetry, not authorization**.  
   **Rejected alternative**: Blocking solely on a classifier.

4. **Seed test-only canary secrets and prohibited values** to make leakage failures deterministic.  
   **Rejected alternative**: Manual visual inspection.

5. **Keep database timeout, request safety timeout, and result limits independent**.  
   **Rejected alternative**: One generic timeout.

## Project Structure

```text
app/security/{classifier.py,validator.py,redaction.py,errors.py}
tests/security/
├── test_prompt_injection.py
├── test_direct_unsafe_requests.py
├── test_authorization.py
├── test_limits_and_timeouts.py
└── test_trace_redaction.py
evaluation/security_cases.json
artifacts/security-results.json
```

## Phases

1. Define attack cases, legitimate controls, and canary values.
2. Harden validator, GraphJin policies, database role, limits, and timeout behavior.
3. Implement stable error categories and trace/error sanitization.
4. Measure security effects, disclosure, and legitimate false refusals.
5. Run complete security validation.

## Validation Gates

```bash
pytest -q tests/security
pytest -q tests/integration/test_conversational_flow.py
```

## Failure Rules

- Any prohibited database effect or disclosed canary value fails the gate.
- Do not relax backend policy to improve classifier false-positive results.
- Do not expose private endpoint details or complete prompts in user-facing traces.

## MANUAL GATE 2: Plan Review

- **Approved**
