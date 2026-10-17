---
type: C4 Actor
title: Analyst
status: stable
groma:
  id: analyst
---

A business or operations analyst who asks plain-English questions about the governed ITSM dataset (tickets, merchants, agents) and expects grounded, provable answers with a sanitized execution trace.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [analyst](analyst.md) | [routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | Asks questions via the demo UI | Browser (FastAPI) |
