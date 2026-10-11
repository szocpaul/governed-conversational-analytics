# Quickstart Validation: DSPy 3.4 Upgrade

**Date**: 2026-10-11 | **Spec**: [spec.md](spec.md) | **Contracts**: [contracts/validation-and-artifacts.md](contracts/validation-and-artifacts.md)

End-to-end validation sequence proving the feature works. Run from the repository root. Prerequisites: the existing stack (PostgreSQL :5432, GraphJin :8081) running; the local llama.cpp endpoint reachable with the pinned model loaded; `.env` configured per `.env.example`.

## 1. Install the upgraded pin

```bash
python3 -m pip install --user -r requirements.txt   # dspy==3.4.0
python3 -c "import dspy, fastapi, pydantic, httpx, pytest; print(dspy.__version__)"
```

Expected: imports succeed on the host Python; `dspy.__version__` is `3.4.0`. If any pinned dependency cannot install or import, STOP AND REPORT.

## 2. Preflight on the new runtime

```bash
python3 -m app.ai.preflight
```

Expected: exit 0; `artifacts/llm-preflight.json` records the exact pinned model ID, a successful deterministic smoke chat completion, a successful typed DSPy prediction, and DSPy 3.4.0.

## 3. Full test suite + deprecation surface

```bash
python3 -m pytest -q
python3 -W default::DeprecationWarning -m pytest -q
```

Expected: all tests pass; the warning-enabled run shows zero DSPy deprecation warnings. Any warning is a finding to fix before continuing (FR-004); an unfixable DSPy-internal warning is a STOP AND REPORT (FR-013).

## 4. Preserve pre-upgrade artifacts

```bash
cp artifacts/baseline.json artifacts/baseline-pre-006-$(date +%F).json
cp artifacts/current.json artifacts/current-pre-006-$(date +%F).json
cp artifacts/optimization-run.json artifacts/optimization-run-pre-006-$(date +%F).json
cp app/ai/optimized_program.json app/ai/optimized_program-pre-006-$(date +%F).json
sha256sum artifacts/baseline{,-pre-006-$(date +%F)}.json   # must match
```

Expected: dated copies exist and are byte-identical to the originals.

## 5. New baseline on 3.4.0

```bash
python3 -W default::DeprecationWarning -m evaluation.run --cache=false --output artifacts/baseline.json
```

Expected: exit 0; temperature 0, cache off, noise block from 2-3 repeated samples, complete held-out run; zero DSPy deprecation warnings in output.

## 6. Re-optimization (dev cases only)

```bash
python3 -W default::DeprecationWarning -m app.ai.optimization
```

Expected: exit 0; `artifacts/optimization-run.json` records the approved BootstrapFewShot config, dev-only input IDs, accepted demo IDs, output SHA-256, and `versions.dspy == "3.4.0"`; `held_out_ids_consumed == 0`. Exit 2 (skip) is a STOP AND REPORT finding.

## 7. Post-optimization held-out evaluation + gate

```bash
python3 -m evaluation.run --cache=false --output artifacts/current.json
python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

Expected: compare exits 0 — no failed P1 thresholds, no execution-accuracy degradation > 5pp, no prohibited effect, no unauthorized disclosure.

## 8. Cross-version report

Produce `artifacts/cross-version-006.json` comparing the preserved 3.2.1 artifacts with the new 3.4.0 artifacts across validity, accuracy, security metrics, false refusals, and latency (per-request, median, p90, max). This report is the human review input at the manual gate; it does not gate.

## 9. Docs

README.md and AGENTS.md pins/status updated to DSPy 3.4.0 and the new artifacts (FR-012).

## Stop conditions (any step)

Install/import failure, preflight failure, test failure, unfixable deprecation warning, optimization skip/failure, compare-gate failure, any prohibited effect or disclosure → STOP AND REPORT per FR-013 and AGENTS.md.
