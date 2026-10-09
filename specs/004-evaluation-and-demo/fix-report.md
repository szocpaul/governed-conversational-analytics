# Fix Report: T010-Review Correctness Findings (F1–F4, F6–F10)

Scope: bounded correctness fixes to the conversational query pipeline
(spec 002/004 code) after human review of spec 004. No spec artifacts,
tasks.md, security policies, PostgreSQL roles, or GraphJin policies were
changed. No GROUP BY/HAVING support was added — unsupported shapes are
rejected cleanly.

## Summary

| Finding | Root cause | Fix | Status after fix |
|---------|-----------|-----|------------------|
| F1 | Multi-part GROUP BY question | Classifier routes multi-part to `ambiguous`; GROUP BY keys rejected if planned | `clarification` |
| F2 | `group_by` silently dropped by `_normalize_shape` → plain count (212) answered as "no data" | Unsupported keys raise `UnsupportedShapeError` → stable `unsupported`, zero GraphJin calls | `unsupported` |
| F3 | Superlative planned as `limit: 1` with no `order_by` → arbitrary row (Alex Mercer 1.061); second question part silently dropped | Tightened planner signature (superlatives MUST set order_by); multi-part → `ambiguous`; re-optimized program | `clarification` (multi-part); single-part superlative answers Samira Khan 1.355 |
| F4 | Grounding proper-noun check treated the question's own filter term ("Account Access") as an ungrounded fact | `is_grounded` accepts phrases/numbers present in the question (query parameters); values absent from BOTH evidence and question stay ungrounded | `answered` 2.34 h |
| F6 | Planner applied `avg` to boolean `resolution_breached` → DB error `avg(boolean) does not exist` | Validator rejects avg/sum on non-numeric fields; planner signature directs boolean ratios to filtered count | `answered` (count 1037) |
| F7 | Planner emitted `order_by` as `[{field, direction}]` → raw pydantic error surfaced as model dependency failure | `_normalize_shape` normalizes the list form; un-normalizable shapes and schema-violating plans map to stable `unsupported` | `answered` or stable category |
| F8 | Same as F2 (`group_by` silently dropped → count 2057 → "no data") | Same as F2 | `unsupported` |
| F9 | Planner filtered integer `merchant_id` with string "Acme Corp" → DB invalid-integer error | Validator type-checks filter values against `COLUMN_TYPES` | `unsupported` |
| F10 | Planner passed null/"None" filter value; no is-null operator exists → DB invalid-integer error | Validator rejects null filter values as unsupported | `unsupported` |

## Root-cause classes and fixes

### Class A — unsupported shapes reaching GraphJin (F1, F2, F6, F8, F9, F10)

The most dangerous bug was the **silent drop**: `_normalize_shape` stripped
unknown keys, so a planner request with `"group_by": ["category"]` was
rewritten into a plain count and executed — returning a plausible but wrong
answer ("No matching data" with count 212/2057). Fixes:

- `app/ai/query_program.py`: `_normalize_shape` now raises
  `UnsupportedShapeError` for keys that express unsupported semantics
  (`group_by`, `having`, `distinct`, `join`, `union`, ...). Zero GraphJin
  calls for such requests; the route maps them to the stable `unsupported`
  category.
- `app/api/schemas.py`: added `COLUMN_TYPES` (mirrors `database/schema.sql`)
  and numeric/orderable aggregate sets.
- `app/security/validator.py`: deterministic type discipline —
  - avg/sum require a numeric field (F6);
  - filter values must be non-null (F10) and type-compatible (F9: no string
    literals on integer columns; timestamps accept ISO strings only);
  - `in` requires a non-empty list of type-compatible values.
- `app/ai/signatures.py`: `PlanQuery` instructions now state the supported
  shapes explicitly (no GROUP BY, typed filter values, avg/sum numeric-only,
  order_by required for superlatives); `ClassifyQuestion` routes multi-part
  questions to `ambiguous` and group-breakdown questions to `unsupported`.

### Class B — schema mismatch (F7)

`order_by` emitted as a list of `{field, direction}` objects is normalized
deterministically to `order_by` + `order_dir`. Multi-field or malformed
order shapes raise `UnsupportedShapeError`. Valid-JSON planner output that
violates the governed schema (pydantic `ValidationError`) is mapped to the
stable `unsupported` category instead of surfacing as a raw model dependency
failure.

### Class C — grounding (F3, F4)

- F4 was a grounding **false negative**: the answer correctly reported 2.34
  but echoed the question's filter term "Account Access", which is not part
  of the aggregate evidence. `is_grounded` now accepts a `question`
  parameter; proper nouns and numbers that appear in the question are query
  parameters, not derived facts.
- F3 detection preserved: a factual value absent from BOTH evidence and
  question remains ungrounded (regression test:
  `test_ungrounded_name_still_detected_with_question`). The wrong-agent
  answer itself is fixed at the planning layer (order_by) and by classifying
  the multi-part question as ambiguous.
- Follow-up found during verification: the answer program once claimed "no
  matching data" when evidence held `count=1037`. `is_grounded` now refuses
  explicit no-data phrasing when evidence contains a non-null aggregate or
  rows, and the `GroundAnswer` signature clarifies that a non-null aggregate
  IS data.

## Re-optimization (approved optimizer only)

DSPy `load_state` restores the saved signature instructions, so the previous
`optimized_program.json` froze the pre-fix instructions. The approved
`dspy.BootstrapFewShot` optimization (unchanged bounded config:
metric_threshold=1.0, max_bootstrapped_demos=4, max_labeled_demos=4,
max_rounds=1, max_errors=3) was re-run on the same 14 development cases:

- accepted demos: DEV-002, DEV-004, DEV-007, DEV-014 (unchanged);
- held-out IDs consumed: 0 (guard asserted);
- new program sha256: cea31477654470293d1861441f1080c686f4bc2294d3686e5e6ffef046f83d0b;
- run artifact: `artifacts/optimization-run.json`.

## Test evidence

- `tests/unit/test_review_findings.py`: 19 deterministic regression tests
  (shape rejection, type checks, order_by normalization, grounding).
- `tests/integration/test_review_findings_live.py`: 10 live end-to-end tests
  running the exact review questions through the pinned LLM + governed
  GraphJin, asserting DB-verified ground truths (F2: P1=49/P2=163; F3:
  Samira Khan 1.355; F4: 2.34; F5 control: 307; F8: Payments & Checkout 483;
  F9: Acme Corp absent; F10: 250 null-agent tickets).
- Full suite: **257 passed** (`python3 -m pytest -q`), up from 228.

## Evaluation gate

```
python3 -m evaluation.run --cache=false --output artifacts/current.json
python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

| Metric | Baseline | Current (post-fix) |
|--------|----------|--------------------|
| Structural validity | 0.9565 | 1.0 |
| Execution accuracy | 0.8125 | 1.0 |
| Prohibited effects | 0 | 0 |
| Disclosures | 0 | 0 |
| False refusals | 3 | 0 |
| Latency median / p90 / max (ms) | 3064 / 3423 / 4325 | 3067 / 3482 / 4011 |

**Compare gate: exit 0.** The execution-accuracy change (+18.75 pp) is a
justified consequence of fixing the buggy behavior the baseline was measured
with: the baseline's three false refusals (EVAL-004, EVAL-006, EVAL-012)
were caused by the F4-class grounding bug and planner misclassification, now
fixed. No held-out case, label, or expectation was modified; the eval set
version is unchanged (1). Latency is observational only and unchanged within
noise.

## Security posture

No security control was relaxed: GraphJin policies, PostgreSQL roles, the
read-only runtime path, redaction, timeouts, and result limits are
untouched. The fixes add deterministic pre-execution rejections only.
Held-out security cases: 0 prohibited effects, 0 disclosures (unchanged).

## Known limitations

- Grouped breakdowns and multi-part questions remain out of scope by design
  (stable `unsupported`/`clarification`); adding GROUP BY is a scope
  expansion requiring a new spec.
- F3-class superlative questions are answered correctly only when the
  planner sets order_by; the tightened signature and re-optimized program do
  this reliably at temperature 0, but there is no deterministic backstop
  that detects a missing order_by for a superlative question.
- The T010 MANUAL GATE itself remains pending and untouched.
