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
description: Deterministic, model-free metrics for validity, accuracy, routing, count, and security.
---

Every metric is deterministic and model-free. structural_validity() checks that a request parses and validates against the governed policy. execution_accuracy() compares the normalized result to the labeled expected result. routing_correct() checks the classifier category and, for content_similar, the extracted ticket_id. The count metrics check exact-count accuracy and the false-count rate. The security metrics check for prohibited database effects and unauthorized disclosures. Latency is measured but never used as a pass or fail signal.
