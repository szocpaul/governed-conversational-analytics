# Implementation Plan: Evaluation, Optimization, and Demo Experience

**Branch**: `[004-evaluation-and-demo]`  
**Date**: 2026-10-09  
**Spec**: [spec.md](spec.md)

## Summary

Create versioned development and held-out datasets, deterministic evaluation metrics, uncached baseline and regression artifacts, a bounded DSPy BootstrapFewShot optimization isolated from held-out cases, and a minimal FastAPI-served interface for demonstrating answers, refusals, traces, and observational latency.

## Technical Context

**Language/Version**: Python 3.12.x, HTML, CSS, JavaScript  
**Primary Dependencies**: DSPy, FastAPI, pytest, existing specs 001 through 003  
**Model Runtime**: Same pinned local llama.cpp Qwen model used by spec 002  
**Optimizer**: `dspy.BootstrapFewShot`  
**Storage**: JSON datasets, optimized DSPy program artifact, and evaluation artifacts  
**Testing**: pytest evaluation, regression, optimization-isolation, and UI/API integration tests  
**Constraints**: Cache disabled for measured runs; held-out set excluded from optimization; latency observational only; no simulated results; GEPA, SIMBA, and MIPROv2 excluded from the first demo

## Constitution Check

- Repository constitution status is not yet verified.
- **MANUAL GATE**: Validate this plan and confirm specs 001 through 003 are complete.

## Architecture

```text
Development cases
    |
BootstrapFewShot
    |  metric: deterministic text-to-query metric
    |  threshold: 1.0
    |  max bootstrapped demos: 4
    |  max labeled demos: 4
    |  max rounds: 1
    v
Versioned optimized DSPy program

Held-out cases ---> uncached evaluation runner
                         |
              deterministic metrics + metadata
                         |
                 baseline/current JSON
                         |
                exit-code comparison gate

Browser UI ---> existing API ---> answer/refusal + trace + latency
```

## Key Decisions

1. **Keep development and held-out cases in separate versioned files**.  
   **Rejected alternative**: One dataset with runtime filtering only.

2. **Use deterministic result comparison for correctness and security**.  
   **Rejected alternative**: LLM judge as the primary gate.

3. **Use `dspy.BootstrapFewShot` as the only optimizer in the first demo** because it is understandable, bounded, suitable for a small labeled development set, and realistic for the local quantized model.  
   **Rejected alternatives**: GEPA, SIMBA, and MIPROv2, because their reflective, candidate-search, mini-batch, or instruction-search workflows add substantially more inference cost and complexity than the first demo requires.

4. **Accept a bootstrapped demonstration only when the optimization metric returns `1.0`**. The metric must require valid structured output, an allowed read-only request, successful governed execution, and an expected normalized result.  
   **Rejected alternative**: Accepting partially correct examples into the prompt.

5. **Use a bounded optimizer configuration**:

```python
optimizer = dspy.BootstrapFewShot(
    metric=text_to_query_metric,
    metric_threshold=1.0,
    max_bootstrapped_demos=4,
    max_labeled_demos=4,
    max_rounds=1,
    max_errors=3,
)
```

   **Rejected alternative**: Unbounded or automatically expanding optimizer budgets.

6. **Require 12 to 20 labeled development examples before optimization is enabled**. If fewer than 12 valid labeled examples exist, record the unoptimized baseline and skip optimization without substituting held-out examples.  
   **Rejected alternative**: Reusing held-out cases to reach an optimizer minimum.

7. **Separate optimization-time generation settings from measured evaluation settings**. BootstrapFewShot may use optimizer-controlled diverse rollouts while creating demonstrations, but baseline and held-out evaluation must use the pinned model, `temperature=0`, and disabled response cache.  
   **Rejected alternative**: Treating optimization candidate generation as a deterministic measurement run.

8. **Measure noise before optimization claims** using repeated uncached sample runs.  
   **Rejected alternative**: Comparing single runs.

9. **Require a new baseline after model, runtime, schema, policy, source-data, optimizer configuration, optimized program, or held-out-data changes**.  
   **Rejected alternative**: Comparing incompatible artifacts.

10. **Keep latency observational** and report per-request, median, p90, and maximum values.  
    **Rejected alternative**: Arbitrary latency threshold before a measured baseline.

11. **Serve a minimal static UI through FastAPI**.  
    **Rejected alternative**: A separate SPA and build system.

## Optimizer Metric Contract

The `text_to_query_metric` returns `1.0` only when all mandatory checks pass:

- structured output validates against the approved request schema;
- the request is read-only and uses only allowed entities, fields, relationships, and operations;
- GraphJin accepts and executes the request successfully;
- the normalized execution result matches the labeled expected result;
- no prohibited effect or unauthorized disclosure occurs.

Otherwise the metric returns `0.0`. Subjective answer wording and latency are not part of the optimizer acceptance metric.

Security attack cases remain in held-out/security evaluation and are not automatically bootstrapped into demonstrations unless explicitly labeled as safe refusal examples in the development set.

## Project Structure

```text
evaluation/
├── dev_cases.json
├── cases.json
├── schemas.py
├── metrics.py
├── run.py
└── compare.py
app/ai/
├── optimization.py
└── optimized_program.json
app/web/{index.html,app.js,styles.css}
artifacts/{baseline.json,current.json,optimization-run.json}
tests/evaluation/
├── test_metrics.py
├── test_regression_gate.py
├── test_optimizer_metric.py
└── test_optimization_isolation.py
tests/integration/test_demo_interface.py
```

## Measurement Discipline

1. Pin code, model artifact, exact API model ID, llama.cpp build when available, parameters, prompts, policy, schema, source data, optimizer type/configuration, optimized-program hash, and evaluation-set versions.
2. Set temperature to zero and disable model-response cache for baseline and held-out evaluation.
3. Run a representative sample two or three times and record per-metric intervals.
4. Record the complete held-out baseline before optimization.
5. Compile BootstrapFewShot only with labeled development cases.
6. Save the optimizer input IDs, configuration, accepted demonstration IDs, output artifact hash, errors, and run metadata to `artifacts/optimization-run.json`.
7. Run the same held-out evaluation and compare each metric independently.
8. Do not claim improvement when observed intervals overlap.

## Validation Gates

```bash
pytest -q tests/evaluation tests/integration/test_demo_interface.py
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

The comparison command returns non-zero for failed P1 quality thresholds, execution-accuracy degradation greater than five percentage points, any prohibited effect, or any unauthorized disclosure. Latency alone never fails the demo gate.

## Phases

1. **Datasets and schemas**: Define versioned development and held-out cases with stable IDs.
2. **Metrics and artifacts**: Implement deterministic metrics, metadata, runner, and comparison gate.
3. **Baseline and noise**: Record repeated-sample noise and the first complete uncached baseline.
4. **BootstrapFewShot optimization**: Implement the binary optimizer metric, compile only on development cases, save the optimized program and optimization metadata, and verify held-out isolation.
5. **Post-optimization evaluation**: Run the unchanged held-out set and compare against baseline.
6. **Demo UI**: Add examples, answer/refusal, sanitized trace, and observational latency.
7. **Final validation**: Run all gates and prepare the human-only demo review.

## Failure Rules

- Stop if the pinned model or a required dependency is unavailable.
- Do not simulate missing evaluation results.
- Do not optimize on held-out identifiers.
- Do not run GEPA, SIMBA, or MIPROv2 in the first demo.
- Do not proceed with BootstrapFewShot when fewer than 12 valid labeled development examples exist.
- Do not accept partial metric scores as bootstrapped demonstrations.
- Do not use latency as a pass/fail target.

## Out-of-Scope Optimizers

- **GEPA**: Reconsider only after a stable BootstrapFewShot baseline exists and a suitable reflection model, textual feedback metric, and explicit optimization budget are approved.
- **MIPROv2**: Reconsider when the development and validation pools are large enough to justify instruction/few-shot candidate search and repeated trials.
- **SIMBA**: Reconsider when the development set can support meaningful mini-batches and the local inference budget supports multiple candidates and steps.
- **Fine-tuning**: Requires a separate specification.

## MANUAL GATE 2: Plan Review

- **Approved with BootstrapFewShot optimizer decision**
