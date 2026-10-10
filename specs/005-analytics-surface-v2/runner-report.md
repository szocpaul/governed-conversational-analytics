# Runner Report: Feature 005 — Analytics Surface v2

**Date**: 2026-10-10
**Runner**: autonomous prime-agent worker (spec005)
**Scope**: tasks T001-T020 (T021 is a MANUAL GATE, left unchecked)
**Branch state**: working tree on `main` (no commits created; see "Commits"
below)

## Outcome

**ALL 20 AUTOMATABLE TASKS COMPLETE.** All validation gates pass. T021
awaits the human reviewer.

## Completed tasks

| Task | Summary | Evidence |
|------|---------|----------|
| T001 | Extended `StructuredQueryRequest`: `group_by` (1-3 allowlisted fields, aggregate-only), `HavingFilter` (function/op/numeric value), `is_null`/`is_not_null` ops (null value only), `ratio` aggregate (boolean field only) | `tests/test_schemas_v2.py` (27 tests) |
| T002 | Validator allowlist re-checks for every new shape + rejection coverage | `tests/test_validator.py` (30 tests) |
| T003 | GraphQL builder: `distinct`+aggregate columns, `is_null`, `avg(expr:{case})` ratio, ratio per group; every rendering verified live before unit expectations | `tests/test_graphql_builder.py` (17 tests) + live probes |
| T004 | Planner normalization: `group_by`/`having` accepted; joins/subqueries/union/distinct-as-key still rejected | `tests/unit/test_query_program.py` (+9 tests) |
| T005 | Grouped-evidence normalization (per-group rows, `groups_truncated`) + end-to-end pipeline | `tests/test_pipeline_groupby.py` |
| T006 | Deterministic application-layer having post-filter (`apply_having`, pure, no DB), `having_applied` evidence, zero-groups clarification | `tests/test_pipeline_groupby.py` |
| T007 | `ClassifyQuestion`/`PlanQuery` docstrings: grouped shapes SUPPORTED, 1-3 field limit, having shape; "NEVER emit group_by" removed; "NEVER output SQL" kept | `app/ai/signatures.py` |
| T008 | Live US1 verification: top category Payments & Checkout 483; P1+P2 after 2026-01-01 per-category (sum 212 = 49+163); having >50 → correct clarification (max per merchant is 32); having >25 → 9 merchants retained | `verification-notes.md` |
| T009 | is_null/is_not_null pipeline tests (count, oldest-open list, presence filter, group_by composition) | `tests/test_pipeline_null.py` (4 tests) |
| T010 | `PlanQuery` docstring: is_null/is_not_null ops, "open = closed_at is_null; closed = is_not_null"; old no-null rule removed for these ops | `app/ai/signatures.py` |
| T011 | Live US2 verification: 250 tickets without assigned agent; 5 oldest open tickets all `closed_at` null, ordered by created_at asc | `verification-notes.md` |
| T012 | Ratio pipeline tests: global ratio in [0,1], empty-base null → clarification, ratio per group | `tests/test_pipeline_ratio.py` (6 tests) |
| T013 | `PlanQuery` ratio rule (replacing "count with filter instead"); `GroundAnswer` percentage formatting, no invented numerator/denominator; `is_grounded` percentage grounding + null-ratio refusal + thousands-separator fix | `app/ai/signatures.py`, `app/ai/answer_program.py` (+6 tests) |
| T014 | Live US3 verification: "50.4% of tickets breached their resolution SLA" grounded in executed ratio 0.5041322314049587 (1037/2057) | `verification-notes.md` |
| T015 | Security tests: group_by on blocked field, ratio on text field, having injection-shaped values, is_null traversal — all rejected with zero GraphJin calls; writes impossible | `tests/test_security_v2.py` (19 tests) |
| T016 | Eval sets extended: dev 14→20 (v2), held-out 23→33 (v2, security 7→11); metrics: grouped comparison (order-sensitive only when labeled) + ratio tolerance 0.001 | `evaluation/{dev_cases,cases}.json`, `evaluation/metrics.py` (+9 tests) |
| T017 | New baseline under feature-004 discipline: 3×8-case noise sample (zero variance), then full 33-case run → `artifacts/baseline.json`; old baseline kept as `artifacts/baseline-pre-005-2026-10-10.json` | `artifacts/baseline.json` |
| T018 | Approved BootstrapFewShot optimization run (20 valid dev examples ≥ 12): 4 accepted demos (DEV-004/005/019/020), 0 held-out consumed | `artifacts/optimization-run.json`, `app/ai/optimized_program.json` |
| T019 | Post-optimization held-out run → `artifacts/current.json`; compare gate exit 0 | `artifacts/current.json` |
| T020 | Full gate set green; README + quickstart + AGENTS.md updated | this report |

## Validation commands and results

| Command | Result |
|---------|--------|
| `python3 -m pytest -q` | **395 passed**, 0 failed (was 257 before the feature) |
| `python3 -m evaluation.run --cache=false --output artifacts/baseline.json` | exit 0; validity 1.0, accuracy 1.0, 0 effects, 0 disclosures, 0 false refusals (33 cases) |
| `python3 -m app.ai.optimization` | exit 0; compiled, 20 dev cases, 4 accepted demos, 0 held-out consumed |
| `python3 -m evaluation.run --cache=false --output artifacts/current.json` | exit 0; validity 1.0, accuracy 1.0, 0 effects, 0 disclosures, 0 false refusals (33 cases, optimized program) |
| `python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json` | **exit 0**, no reasons |

## Metrics (held-out, eval-set v2, 33 cases = 22 analytics + 11 security)

| Metric | Baseline (T017) | Current (T019, optimized) |
|--------|-----------------|---------------------------|
| Structural validity | 1.0 | 1.0 |
| Execution accuracy | 1.0 | 1.0 |
| Prohibited effects | 0 | 0 |
| Disclosures | 0 | 0 |
| False refusals | 0 | 0 |
| Latency median / p90 / max (observational) | 2907 / 3282 / 3794 ms | 2924 / 3350 / 3849 ms |

Noise (T017): 3 × 8-case representative sample — accuracy [1.0, 1.0, 1.0],
validity [1.0, 1.0, 1.0]; zero variance (temperature 0, cache disabled).

## Ground-truth verification (spec SC-001)

| Question | Expected | Observed |
|----------|----------|----------|
| Which category has the most tickets? | Payments & Checkout, 483 | answered, 483 in evidence |
| P1/P2 after 2026-01-01 by category | P1=49, P2=163 (Σ212) | per-category counts Σ=212 |
| Tickets with no assigned agent | 250 | answered 250 |
| SLA breach percentage | 50.4% (1037/2057) | answered 50.4%, ratio 0.50413223… |

## Security results (SC-002, SC-006)

- 19 new abuse tests (group_by on blocked field, ratio on text field,
  having injection values, is_null traversal, write shapes) — all rejected
  deterministically before any GraphJin call.
- 11 held-out security cases (7 pre-existing + 4 new operator-abuse):
  all refused/handled with zero prohibited effects and zero disclosures.
- Read-only path unchanged: no mutations added; GraphJin role/policy and
  the PostgreSQL read-only role untouched.

## Files changed

Application: `app/api/schemas.py`, `app/security/validator.py`,
`app/data/graphjin_client.py`, `app/data/result_normalizer.py`,
`app/ai/signatures.py`, `app/ai/query_program.py`,
`app/ai/answer_program.py`, `app/ai/optimization.py`, `app/api/routes.py`,
`app/ai/optimized_program.json` (regenerated by T018).

Evaluation: `evaluation/dev_cases.json` (v2), `evaluation/cases.json` (v2),
`evaluation/metrics.py`, `evaluation/run.py`.

Tests added: `tests/test_schemas_v2.py`, `tests/test_validator.py`,
`tests/test_graphql_builder.py`, `tests/test_pipeline_groupby.py`,
`tests/test_pipeline_null.py`, `tests/test_pipeline_ratio.py`,
`tests/test_security_v2.py`; extended: `tests/unit/test_query_program.py`,
`tests/unit/test_answer_program.py`, `tests/evaluation/test_metrics.py`.

Tests updated for the approved behavior change (spec 005 FR-001 makes
group_by/is-null supported, reversing the spec-004 rejection findings):
`tests/unit/test_review_findings.py` (F2/F8 group_by now parsed, aliases
still rejected), `tests/integration/test_review_findings_live.py` (F8 live
test now asserts the grounded Payments & Checkout 483 answer).

Docs/artifacts: `README.md`, `AGENTS.md`,
`specs/005-analytics-surface-v2/quickstart.md` (observed results),
`specs/005-analytics-surface-v2/verification-notes.md` (new),
`artifacts/baseline.json`, `artifacts/current.json`,
`artifacts/optimization-run.json`,
`artifacts/baseline-pre-005-2026-10-10.json` (audit copy),
`artifacts/optimized_program-pre-005-2026-10-10.json` (audit copy).

## Decisions and assumptions (reported per harness rules)

1. **Stale optimized program moved aside**: the spec-004
   `optimized_program.json` embedded the old "no GROUP BY" instructions and
   masked the new surface during T008. Moved to
   `artifacts/optimized_program-pre-005-2026-10-10.json`; T018 regenerated a
   fresh optimized program on the extended dev set (approved config only).
2. **"Merchants with more than 50 tickets" yields a clarification — this is
   CORRECT**: the pinned dataset's maximum tickets per merchant is 32
   (verified directly). The spec scenario illustrates the having shape, not
   a labeled ground truth. The positive path was verified with ">25" (9
   merchants).
3. **Grounding check extended, not weakened**: `is_grounded` now treats a
   `ratio_*` fraction as grounding its exact percentage form (0.5041… ↔
   "50.4"), refuses any percentage when the ratio is null, and normalizes
   thousands separators ("1,807" ↔ 1807). All pre-existing grounding tests
   still pass.
4. **Two spec-004 tests updated** (listed above) because spec 005 explicitly
   approves the behavior they prohibited; every other pre-existing test
   passes unchanged (FR-011/SC-004).
5. **`artifacts/import-manifest.json` timestamp moved** as a byproduct of
   the idempotent import test in the full suite; dataset content, checksums,
   and row counts are byte-identical.
6. Test file placement follows tasks.md literally (`tests/test_*.py` at the
   repo-root tests dir) alongside the existing `tests/unit/` layout.

## Pinned versions

- Python 3.12, pytest 9.0.3, dspy 3.2.1
- GraphJin 3.21.6 (`dosco/graphjin:3.21.6`), PostgreSQL 16.10-alpine
- Model: `models\Qwen3.8-27B-UD-Q4_K_M.gguf` via local llama.cpp
  (OpenAI-compatible endpoint), temperature 0, cache disabled
- Dataset: commit `cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b` (unchanged)
- Optimized program SHA-256:
  `421b664260b97ac9df3516111a28e7591ae2971d1207c285077dbe673e91f235`

## Commits

None created (the runner leaves committing to the reviewer/launcher; the
working tree contains all changes, traceable to task IDs in this report).

## Known limitations

- Having is an application-layer post-filter over the returned group page;
  when `groups_truncated` is true the answer reflects possible truncation
  (documented in research.md Decision 4; flagged in evidence).
- Ratio v1 supports boolean-flag ratios only (per the approved contract).
- Multi-part questions remain out of scope (unchanged from spec 004).

## Outstanding manual gate

**T021 MANUAL GATE** — human reviewer runs the quickstart scenarios
(grouped, having, is-null, ratio, abuse rejection), reviews
`artifacts/baseline.json` / `artifacts/current.json` /
`artifacts/optimization-run.json`, the security results, and eval-set
isolation (dev v2 / held-out v2, zero held-out IDs in optimization), then
approves or rejects the release. The implementation agent has NOT ticked
T021.

**Exact human decision required**: approve or reject the feature 005
release per `specs/005-analytics-surface-v2/tasks.md` T021.
