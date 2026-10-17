---
type: C4 Component
title: Deterministic evaluation metrics
status: stable
groma:
  id: metrics
  parent: evaluation
  code:
    - scanner: python
      file: evaluation/metrics.py
  group: Metrics & gates
description: Deterministic, model-free metrics for structural validity, execution accuracy, routing, count, and security.
---

Every metric is deterministic and model-free. structural_validity() checks that a request parses and validates against the policy. execution_accuracy() compares the normalized result to the labeled expected result. routing_correct() checks the classifier category (and, for content_similar, the extracted ticket_id). count metrics check exact-count accuracy and false-count rate. Security metrics check for prohibited database effects and unauthorized disclosures. Latency is observational only.
