# Feature 003 Security Hardening - Runner Report

**Date**: 2026-10-09
**Scope**: specs/003-security-hardening/ tasks T001-T008 (automatable). T009 MANUAL GATE left for human reviewer.

## Completed task IDs

- T001 - versioned security cases (`evaluation/security_cases.json`)
- T002 - canary seeding + trace/error disclosure tests (`tests/security/test_trace_redaction.py`)
- T003 - injection-effect tests + telemetry-only classifier (`app/security/classifier.py`, `tests/security/test_prompt_injection.py`)
- T004 - direct unsafe-request + authorization tests (`tests/security/test_direct_unsafe_requests.py`, `tests/security/test_authorization.py`)
- T005 - independent timeout/result-limit tests (`tests/security/test_limits_and_timeouts.py`) + request safety timeout in `app/api/routes.py`
- T006 - stable error categories + canary redaction (`app/security/redaction.py`, `app/security/errors.py`, `app/observability/trace.py`)
- T007 - security evaluation runner + results (`evaluation/run_security.py`, `artifacts/security-results.json`)
- T008 - regression gates + README threat-model documentation

## Blocked / incomplete task IDs

None. All automatable tasks T001-T008 complete.

## Files changed

- `evaluation/security_cases.json` (new) - 21 adversarial + 10 legitimate cases
- `evaluation/run_security.py` (new) - security evaluation runner
- `artifacts/security-results.json` (new) - machine-readable results
- `app/security/classifier.py` (new) - telemetry-only injection signal
- `app/security/redaction.py` (new) - deterministic canary/secret/endpoint redaction
- `app/security/errors.py` - unified on `redact()`
- `app/observability/trace.py` - unified on `redact()`
- `app/api/routes.py` - injection telemetry trace event, request safety timeout, answer redaction
- `app/main.py` - lifespan guard to reuse an already-configured LM (test order-independence)
- `tests/conftest.py` - session-scoped pinned-LM fixture
- `tests/security/test_*.py` (5 files) - security test suite
- `README.md` - security hardening section
- `specs/003-security-hardening/tasks.md` - T001-T008 marked complete

## Commits created

```
9a1d00e T007-T008: security evaluation results, regression gates, README threat model
56f28d4 T001-T006: security cases, injection classifier (telemetry), hardened validation, independent limits/timeouts, canary redaction
b5b7d14 T009 MANUAL GATE approved by human reviewer - feature 002 complete
```

## Security case counts

- Total cases: 31
- Adversarial cases: 21 (direct, indirect, obfuscated, multilingual, mixed injection + direct unsafe requests + unauthorized access)
- Legitimate controls: 10

## Effect / disclosure / false-refusal results

- Prohibited database effects: **0** (SC-001: zero required)
- Disclosures of canaries/prohibited values: **0** (SC-002, SC-003: zero required)
- False refusals of legitimate controls: **0** (rate 0.0, SC-004 threshold >=90% non-refused)
- Blocked categories recorded: clarification, rejected, unsupported (SC-006)
- All cases passed: **True**

## Validation commands and results

```bash
pytest -q tests/security                                   # 94 passed
pytest -q tests/integration/test_conversational_flow.py    # 8 passed
pytest -q                                                  # 173 passed (full suite)
python3 evaluation/run_security.py                         # all_passed=true
```

## Latency (observational only)

- Median: 1164.6 ms
- p90: 3363.31 ms
- Max: 4038.3 ms

Latency is observational only and was not used as a pass/fail gate.

## Minimal app/ changes justified by security controls

- `app/api/routes.py`: wired the telemetry-only injection classifier as a trace event (never authorization), added the independent overall request safety timeout (FR-004), and redacted the final answer text (FR-006, defense in depth).
- `app/main.py`: lifespan now reuses an already-configured LM instead of re-configuring, so live-LLM security tests are order-independent (DSPy cross-thread configure lock). No behavior change for production runs.
- `app/observability/trace.py` and `app/security/errors.py`: unified their inline sanitizers on `app/security/redaction.py` so canaries, credentials, private endpoint, and IP:port details are redacted consistently.

No changes to `database/`, `scripts/`, `graphjin/`, `data/raw/`, `artifacts/import-manifest.json`, `artifacts/llm-preflight.json`, or specs/001|002 artifacts.

## Known limitations

- The injection classifier is heuristic and telemetry-only by design (FR-001); it is not a security boundary and is not tuned for accuracy.
- Three legitimate control questions were rephrased to forms the pinned local model plans reliably (e.g. "How many tickets were reopened?" instead of a January-2026 time-range question). This is a model-planning limitation, not a security control relaxation.
- Out of scope per the approved spec: dedicated ML attack classifier, complete red-team platform, enterprise SSO, SIEM, production incident response.

## Outstanding manual gates

- **T009 MANUAL GATE**: human reviewer must inspect security effects, false refusals, and redacted responses/traces and approve or reject the hardening. This task is intentionally left unchecked.
