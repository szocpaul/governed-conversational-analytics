---
type: C4 Component
title: GraphJin GraphQL client
status: stable
groma:
  id: graphjin-client
  parent: web-application
  code:
    - scanner: python
      file: app/data/graphjin_client.py
    - scanner: python
      file: app/data/__init__.py
  group: Data access
description: Builds a governed GraphQL query from a typed request and executes it against the GraphJin surface.
---

The only database access path for the runtime structured-query flow. Builds a GraphQL query string from a validated StructuredQueryRequest: list operations select fields with optional where, order_by, limit; aggregate operations use count, ratio (aliased expression aggregate), or fn_field; grouped operations use distinct + aggregate columns. HAVING is not rendered (GraphJin v3 has no native HAVING) — the post-aggregation filter is applied client-side by result_normalizer. No arbitrary SQL is ever constructed or sent.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/data/graphjin_client.py](../../../../../../app/data/graphjin_client.py) | [app/api/schemas.py](../../../../../../app/api/schemas.py) | Builds query from typed request | Python (Pydantic) |
| [graphjin-client](graphjin-client.md) | [graphjin](../../../../../externals/graphjin.md) | Sends governed GraphQL queries | HTTP GraphQL |
