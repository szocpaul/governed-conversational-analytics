# Implementation Plan: Analytics Surface v2

**Branch**: `005-analytics-surface-v2` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-analytics-surface-v2/spec.md`

## Summary

Extend the governed conversational analytics surface with three capabilities
confirmed missing in the spec 004 T010 review: (1) grouped aggregations
(GROUP BY), (2) missing-value filtering (is-null / is-not-null), and
(3) ratio/percentage metrics as a dedicated aggregate. All three map onto
native GraphJin v3.21.6 GraphQL capabilities verified live against the
running stack: grouped summaries via `distinct: [col]` + aggregate columns
(`count_<field>`, `avg_<field>`, ...), null filtering via
`{field: {is_null: true}}`, and ratios via expression aggregates
(`avg(expr: {case: {arms: [...], else: 0}})`). GraphJin v3 has **no native
HAVING** (verified in source and live), so post-aggregation group filtering
is implemented as a deterministic application-layer filter over the returned
groups (documented in research.md). The deterministic validator remains the
boundary: every new shape is explicitly allowlisted and re-checked before any
GraphJin call. New evaluation cases extend the versioned dev/held-out sets,
and a new baseline is recorded under feature 004 discipline.

## Technical Context

**Language/Version**: Python 3.12 (existing project)

**Primary Dependencies**: DSPy 3.x (planner/answer programs), FastAPI + pydantic (typed request surface), httpx (GraphJin client), GraphJin 3.21.6 (pinned image `dosco/graphjin:3.21.6`), PostgreSQL 16.10-alpine (pinned)

**Storage**: PostgreSQL `itsm` schema (existing, unchanged); versioned JSON evaluation sets (`evaluation/dev_cases.json`, `evaluation/cases.json`)

**Testing**: pytest (unit + integration + security), evaluation harness (`python -m evaluation.run`, `python -m evaluation.compare`)

**Target Platform**: Linux server, Docker Compose local stack

**Performance Goals**: none (latency is observational only per project constitution)

**Constraints**: read-only governed surface; no arbitrary SQL; validator is the deterministic boundary; temperature 0, cache disabled for measured runs; held-out evaluation isolation; no new database writes

**Scale/Scope**: 3 query-surface capabilities + planner/signature updates + validator allowlist + GraphQL builder + eval set extension + new baseline; ~6 source files touched, ~4 test files extended/added

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`.specify/memory/constitution.md`) is an
unpopulated template; project governance lives in `AGENTS.md`. Check against
AGENTS.md absolute prohibitions and workflow rules:

- ✅ No arbitrary SQL; GraphJin remains the only database access path.
- ✅ Read-only runtime path preserved; no writable roles or mutations added.
- ✅ No model/provider switch; same local llama.cpp endpoint and pinned model.
- ✅ Tests first, observed failing, per AGENTS.md implementation workflow.
- ✅ Held-out evaluation isolation preserved; new cases added with stable IDs,
  version bump, zero held-out IDs consumed by optimization.
- ✅ No GEPA/MIPROv2/SIMBA/fine-tuning; optimization, if run, uses only the
  approved BootstrapFewShot configuration on dev examples.
- ✅ Latency remains observational; no latency pass/fail gate.
- ✅ No real organizational or personal data; pinned synthetic dataset unchanged.
- ✅ No secrets committed; endpoint details stay out of user-facing traces.

No violations. Complexity Tracking: not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-analytics-surface-v2/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── structured-query-request-v2.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── api/
│   └── schemas.py              # StructuredQueryRequest: +group_by, +having, +is_null ops, +ratio aggregate
├── ai/
│   ├── signatures.py           # PlanQuery/ClassifyQuestion docstring updates for new shapes
│   ├── query_program.py        # shape normalization: allow new keys, keep rejecting true unsupported
│   └── answer_program.py       # grounding for grouped rows + ratio evidence (percent formatting)
├── security/
│   └── validator.py            # allowlist checks for group_by/having/is_null/ratio
├── data/
│   └── graphjin_client.py      # build_graphql: distinct groups, is_null, expr ratio, post-agg filter
└── observability/              # trace events for new stages (unchanged interface)

evaluation/
├── dev_cases.json              # +new dev cases (version bump)
├── cases.json                  # +new held-out cases incl. security abuse cases (version bump)
├── metrics.py                  # grouped/ratio result normalization for scoring
└── run.py                      # unchanged interface

tests/
├── test_validator.py           # new-shape allowlist + rejection tests
├── test_graphql_builder.py     # distinct/is_null/expr-ratio rendering tests
├── test_pipeline_groupby.py    # end-to-end grouped/ratio/null pipeline tests
└── test_security_v2.py         # abuse cases: new operators reaching non-allowlisted fields

artifacts/
└── baseline.json               # re-recorded after extension (feature 004 discipline)
```

**Structure Decision**: extend the existing single-project layout; no new
top-level packages. All changes are additive to the existing governed
pipeline (schemas → planner → validator → GraphQL builder → answer).

## Phase Summary

- **Phase 0 (research.md)**: GraphJin v3 grouped-summary, null-filter, and
  expression-aggregate capabilities verified live against the running stack;
  HAVING absence confirmed in source; post-aggregation filter decision
  documented. All NEEDS CLARIFICATION resolved.
- **Phase 1 (data-model.md, contracts/, quickstart.md)**: typed request v2
  shape, grouped/ratio evidence model, contract for the extended request
  surface, and runnable validation scenarios.

## Complexity Tracking

No constitution violations; section intentionally empty.
