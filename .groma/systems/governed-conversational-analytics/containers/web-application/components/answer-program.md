---
type: C4 Component
title: Answer program
status: stable
groma:
  id: answer-program
  parent: web-application
  code:
    - scanner: python
      file: app/ai/answer_program.py
  group: Query pipeline
description: DSPy module that generates a grounded answer from execution evidence, with a deterministic grounding check.
---

Generates an answer from the question plus normalized evidence via the GroundAnswer predictor. A deterministic is_grounded() check verifies every factual token (numbers, named values, ratios) in the answer appears in the evidence; ungrounded answers are flagged so the caller can refuse. Handles empty evidence (no-data), null ratios (undefined), grouped results, and ratio percentages. Query parameters echoed from the question are not treated as hallucinations.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/ai/answer_program.py](../../../../../../app/ai/answer_program.py) | [app/ai/signatures.py](../../../../../../app/ai/signatures.py) | Uses GroundAnswer signature | Python (DSPy) |
| [answer-program](answer-program.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Grounds the answer in the evidence | DSPy (pinned local model) |
