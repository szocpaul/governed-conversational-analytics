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
description: Pydantic models and loaders for the dev and held-out evaluation case sets.
---

Defines the EvalCase and EvalCaseSet models and provides load_dev_cases() and load_held_out_cases() to load the physically separated evaluation/dev_cases.json and evaluation/cases.json. Each case carries a stable unique ID, the question, a category, and an expected result (a labeled governed request and/or normalized result, a routing label, or a security effect expectation). The separation is enforced here: development cases feed optimization and calibration, held-out cases feed evaluation only, and no held-out ID may enter optimization or calibration. The security cases in evaluation/security_cases.json are loaded separately by the security runner.
