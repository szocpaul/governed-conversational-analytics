# Contracts: DSPy 3.4 Upgrade

**Date**: 2026-10-11 | **Spec**: [spec.md](../spec.md)

This feature exposes no new external API and changes no existing endpoint. Its contracts are the validation commands (the project's governed entry points, unchanged) and the artifact format guarantees the feature must uphold.

## Validation command contract

The following commands MUST exist and behave as specified at feature completion:

| Command | Expected result |
|---|---|
| `python3 -m pytest -q` | exit 0; all tests pass on DSPy 3.4.0 |
| `python3 -m app.ai.preflight` (or the existing preflight entry point) | exit 0; `artifacts/llm-preflight.json` written with the exact pinned model ID and DSPy 3.4.0 |
| `python3 -m evaluation.run --cache=false --output artifacts/baseline.json` | exit 0; new 3.4.0 baseline with noise block and pinned metadata |
| `python3 -m app.ai.optimization` | exit 0 (or 2 with a recorded skip if <12 valid dev examples — which itself is a stop-and-report finding); `artifacts/optimization-run.json` records inputs, accepted demo IDs, config, output hash, errors, versions |
| `python3 -m evaluation.run --cache=false --output artifacts/current.json` | exit 0; post-optimization held-out results |
| `python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json` | exit 0; no failed P1 thresholds, no execution-accuracy degradation > 5pp, no prohibited effect, no unauthorized disclosure |

Deprecation-surface contract: each measured command above, when run as `python3 -W default::DeprecationWarning -m ...`, MUST produce zero DSPy deprecation warnings in its output before the baseline step is considered valid (FR-004).

## Artifact contracts

- **Preserved artifacts** (`*-pre-006-YYYY-MM-DD.json`): byte-identical copies of their pre-upgrade sources; SHA-256 of source and copy recorded; immutable after creation.
- **`artifacts/llm-preflight.json`**: contains exact API model ID, DSPy version, timestamp, and non-secret check results; MUST NOT contain credentials or private endpoint details.
- **`artifacts/baseline.json` / `artifacts/current.json`**: existing schema, with metadata recording DSPy 3.4.0 and the Python version.
- **`artifacts/optimization-run.json`**: existing schema; `versions.dspy` == "3.4.0"; `held_out_ids_consumed` == 0; accepted demo IDs ⊆ dev case IDs.
- **`artifacts/cross-version-006.json`**: per-version validity, accuracy, security metrics, false-refusal rate, latency (per-request, median, p90, max), plus artifact hashes and runtime metadata. Never produces a pass/fail gate verdict.

## UI / endpoint contract

No change. The demo UI, API routes, and GraphJin boundary are untouched; the private LLM endpoint remains unexposed in UI, errors, and traces.
