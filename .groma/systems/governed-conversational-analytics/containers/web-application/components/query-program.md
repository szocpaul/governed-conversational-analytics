---
type: C4 Component
title: Query program
status: stable
groma:
  id: query-program
  parent: web-application
  code:
    - scanner: python
      file: app/ai/query_program.py
  group: Query pipeline
description: DSPy module that classifies a question and, if supported, plans a typed governed query request.
---

Composes two typed predictors: ClassifyQuestion (routes to content_about, content_similar, content_count, supported, ambiguous, or unsupported) and PlanQuery (emits a JSON StructuredQueryRequest). The planner output is parsed into a validated StructuredQueryRequest against the governed allowlist. Unsupported query shapes (joins, subqueries, unions, distinct-as-key) raise UnsupportedShapeError before any GraphJin call. The conservative fallback routes unknown classifier output to the structured path.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/ai/query_program.py](../../../../../../app/ai/query_program.py) | [app/ai/signatures.py](../../../../../../app/ai/signatures.py) | Composes typed predictors | Python (DSPy) |
| [app/ai/query_program.py](../../../../../../app/ai/query_program.py) | [app/ai/routing.py](../../../../../../app/ai/routing.py) | Normalizes category | Python (pure function) |
| [app/ai/query_program.py](../../../../../../app/ai/query_program.py) | [app/api/schemas.py](../../../../../../app/api/schemas.py) | Parses planner output | Python (Pydantic) |
| [query-program](query-program.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Classifies and plans the question | DSPy (pinned local model) |
