---
type: C4 Component
title: DSPy signatures
status: stable
groma:
  id: signatures
  parent: web-application
  code:
    - scanner: python
      file: app/ai/signatures.py
    - scanner: python
      file: app/ai/__init__.py
  group: Query pipeline
description: Typed DSPy Signature definitions for the classifier, planner, and grounded answer.
---

Three signatures: ClassifyQuestion (routes a question to exactly one category), PlanQuery (plans a typed governed GraphQL request with a strict entity/field/operation allowlist, supporting list and aggregate operations with filters, group_by, having, ratio, and is_null/is_not_null), and GroundAnswer (answers using only the provided execution evidence). PROMPT_VERSION is bumped on any instruction change. No hard-coded prompt strings; the instruction lives in the Signature docstring.
