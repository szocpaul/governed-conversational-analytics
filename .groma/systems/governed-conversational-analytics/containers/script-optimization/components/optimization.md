---
type: C4 Component
title: BootstrapFewShot optimization
status: stable
groma:
  id: optimization
  parent: script-optimization
  code:
    - scanner: python
      file: app/ai/optimization.py
description: Bounded BootstrapFewShot optimization on development cases only.
---

app/ai/optimization.py runs the approved dspy.BootstrapFewShot optimizer with the bounded configuration (metric_threshold 1.0, max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors 3). The binary metric returns 1.0 only when every mandatory check passes: the structured output validates, the request is read-only and policy-allowed, GraphJin executes successfully, the normalized result matches the labeled expected result, and no prohibited effect or unauthorized disclosure occurs.

Only development case IDs are consumed and the held-out IDs are guarded against leakage. The run saves the optimized program, the accepted demonstration IDs, the configuration, the artifact hashes, the errors, and the pinned versions to artifacts/optimization-run.json. GEPA, MIPROv2, SIMBA, and fine-tuning are prohibited and are not used.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [optimization](optimization.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Runs BootstrapFewShot optimization | DSPy (pinned local model) |
