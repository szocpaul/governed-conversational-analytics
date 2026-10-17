---
type: C4 Component
title: Evaluation case schemas
status: stable
groma:
  id: evaluation-schemas
  parent: evaluation
  code:
    - scanner: python
      file: evaluation/schemas.py
    - scanner: python
      file: evaluation/__init__.py
  group: Case schemas
description: Pydantic models and loaders for the dev and held-out evaluation case sets.
---

Defines the EvalCase and EvalCaseSet models and provides load_dev_cases() and load_held_out_cases() to load the physically separated evaluation/dev_cases.json and evaluation/cases.json. Each case carries a stable unique ID, the question, a category, and an expected result (labeled governed request and/or normalized result, or a routing label, or a security effect expectation). The separation is enforced: dev cases are used for optimization, held-out cases for evaluation; zero held-out IDs may enter optimization.
