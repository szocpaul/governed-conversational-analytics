# Data Model: DSPy 3.4 Upgrade

**Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

This feature changes no database schema and no query-surface data structures. Its entities are the versioned artifacts that record the measured state before and after the upgrade.

## Entities

### Preserved pre-upgrade artifacts

Byte-identical dated copies of the 3.2.1-era measured state, created before any re-measurement (FR-005). Naming follows the feature 005 convention.

- `artifacts/baseline-pre-006-YYYY-MM-DD.json` — copy of the pre-upgrade `artifacts/baseline.json`.
- `app/ai/optimized_program-pre-006-YYYY-MM-DD.json` — copy of the pre-upgrade `app/ai/optimized_program.json` (3.2.1-compiled).
- `artifacts/current-pre-006-YYYY-MM-DD.json` and `artifacts/optimization-run-pre-006-YYYY-MM-DD.json` — copies of the pre-upgrade post-optimization evaluation and optimization record, so the cross-version report has the complete 3.2.1 evidence set.

Validation rules:
- Each copy MUST be byte-identical to its source (SHA-256 match recorded).
- Once created, preserved copies MUST NOT be modified by any later step.

### Regenerated measured artifacts (3.4.0)

- `artifacts/llm-preflight.json` — non-secret preflight metadata: exact API model ID, endpoint reachability, smoke chat completion result, typed DSPy prediction result, DSPy version. MUST NOT contain credentials or private endpoint details beyond the already-approved non-secret fields.
- `artifacts/baseline.json` — new 3.4.0 baseline under feature 004 discipline. Required metadata: code version, model ID, temperature 0, cache false, DSPy version, Python version, noise block (sample size, repetitions, per-metric values), eval set version.
- `artifacts/optimization-run.json` — optimizer: `dspy.BootstrapFewShot`; config (metric_threshold 1.0, max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors 3); input case IDs (dev only); accepted demo IDs; output program SHA-256; errors; versions (dspy 3.4.0, model ID, temperature, cache).
- `app/ai/optimized_program.json` — state-only compiled program produced on 3.4.0.
- `artifacts/current.json` — post-optimization held-out evaluation on 3.4.0 (temperature 0, cache off).

### Cross-version report

- `artifacts/cross-version-006.json` — comparison of the preserved 3.2.1 results vs the 3.4.0 results. Fields per version: structural validity, execution accuracy, prohibited-effect count, unauthorized-disclosure count, false-refusal count/rate, latency (per-request values, median, p90, maximum). Includes both versions' artifact hashes and runtime metadata (DSPy version, Python version, model ID). Not gated; human review item (FR-009).

### Evaluation case sets (unchanged)

- `evaluation/dev_cases.json` and `evaluation/cases.json` — physically separate, versioned; content unchanged by this feature; consumed under existing isolation rules (zero held-out IDs into optimization).

## State transitions

```text
pre-upgrade artifacts
    --(preserve, byte-identical)--> *-pre-006-*.json (immutable)
3.4.0 runtime verified (preflight + tests + zero warnings)
    --(baseline discipline)--> artifacts/baseline.json (3.4.0)
    --(approved BootstrapFewShot, dev only)--> app/ai/optimized_program.json + artifacts/optimization-run.json
    --(held-out run)--> artifacts/current.json
    --(same-version compare gate)--> PASS required
preserved 3.2.1 + new 3.4.0 results
    --(cross-version report)--> artifacts/cross-version-006.json --> human manual gate
```

Any failure at the runtime-verification stage (install failure, test failure, unfixable deprecation warning, preflight failure) transitions the feature to STOP AND REPORT (FR-013) instead of proceeding to re-measurement.
