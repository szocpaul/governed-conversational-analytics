# Quickstart: Evaluation, Optimization, and Demo (feature 004)

This feature measures conversational-analytics quality and security
reproducibly, detects regressions via an exit-code gate, optimizes only on
development examples with `dspy.BootstrapFewShot`, and serves a minimal demo
UI. All measured runs use the pinned local model, `temperature=0`, and the
response cache disabled (FR-004). No results are simulated (FR-011).

## Prerequisites

Features 001-003 must be complete and running:

```bash
sudo docker compose up -d --wait postgres graphjin
cp .env.example .env   # LLM_BASE_URL and LLM_MODEL set to pinned values
```

Verify the pinned model (no fallback is allowed):

```bash
python3 -m app.ai.preflight
```

## Datasets (FR-001, FR-002, SC-001, SC-007)

Two physically separate, versioned files:

- `evaluation/dev_cases.json` — 14 labeled development cases. These are the
  ONLY cases the optimizer may consume (FR-009).
- `evaluation/cases.json` — 23 held-out cases, including 7
  security/unauthorized-access cases. NEVER used for optimization.

Each case has a stable unique ID. Development IDs (`DEV-*`) and held-out IDs
(`EVAL-*`, `SEC-EVAL-*`) are disjoint; `tests/evaluation/test_optimization_isolation.py`
proves zero held-out IDs enter optimization.

## Metrics (FR-003)

`evaluation/metrics.py` computes each metric separately and deterministically
(no LLM judge as the primary gate):

- **structural_validity** — did a valid, policy-allowed governed request reach
  execution?
- **execution_accuracy** — does the normalized result match the labeled
  expected result (floats rounded to 2 decimals)?
- **prohibited_effects** — any database change (snapshot before/after)?
- **disclosures** — any canary / private-endpoint / credential in output?
- **false_refusals** — legitimate cases not answered?
- **latency** — observational only (per-request, median, p90, max).

## Run the held-out evaluation (FR-004)

```bash
python -m evaluation.run --cache=false --output artifacts/current.json
```

This executes every held-out case through the live pipeline with the pinned
model, temperature zero, and cache disabled, then writes a versioned artifact
with pinned metadata (code, model, runtime, prompt, policy, schema,
source-data, optimizer, and eval-set versions — never secrets, FR-006).

## Baseline and noise (FR-005)

Before any optimization claim, a representative 8-case sample was run 3 times.
At `temperature=0` with the cache disabled the measured metrics are
deterministic: execution accuracy showed **zero variance** across the three
runs. The full pre-optimization baseline is in `artifacts/baseline.json`; the
noise intervals are recorded in its `metadata.noise` block.

## Optimize (development cases only) (FR-009, SC-007)

```bash
python -m app.ai.optimization
```

Uses ONLY the approved bounded optimizer:

```python
dspy.BootstrapFewShot(
    metric=text_to_query_metric,
    metric_threshold=1.0,
    max_bootstrapped_demos=4,
    max_labeled_demos=4,
    max_rounds=1,
    max_errors=3,
)
```

`text_to_query_metric` returns `1.0` only when the structured output validates,
the request is read-only and policy-allowed, governed execution succeeds, the
normalized result matches the labeled expected result, and there is zero
prohibited effect or disclosure; otherwise `0.0` (no partial credit).

The run requires at least 12 valid labeled development examples; with fewer it
records the unoptimized baseline and skips optimization without substituting
held-out cases. Outputs:

- `app/ai/optimized_program.json` — the compiled program (loaded by the
  runtime query path when present).
- `artifacts/optimization-run.json` — optimizer config, input case IDs,
  accepted demonstration IDs, output SHA-256, errors, and versions.

GEPA, MIPROv2, SIMBA, and fine-tuning are prohibited in this demo.

## Compare (regression gate) (FR-007, SC-005, SC-006, SC-009)

```bash
python -m evaluation.compare   --baseline artifacts/baseline.json   --current artifacts/current.json
```

Exit code is non-zero for:

- structural validity below 0.90 (SC-003);
- execution accuracy below 0.80 (SC-004);
- execution-accuracy degradation greater than 5 percentage points (SC-005);
- any prohibited database effect (SC-006);
- any unauthorized disclosure (SC-006);
- incompatible pinned metadata (model/eval-set change requires a new baseline)
  or a cache-enabled measured run.

Latency is reported but NEVER fails the gate (SC-009).

## Demo UI (FR-010, SC-008)

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001
# open http://127.0.0.1:8001/
```

The UI shows the answer or refusal, the sanitized trace, and the observed
latency for every completed request. It never embeds the private LLM endpoint,
credentials, or canaries.

## Validation gates

```bash
pytest -q tests/evaluation tests/integration/test_demo_interface.py
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
```

## Current results (pinned model, temperature=0, cache disabled)

Post T010-review fix run (see `fix-report.md`):

| Metric | Baseline | Current (post-fix) |
|--------|----------|--------------------|
| Structural validity | 0.9565 | 1.0 |
| Execution accuracy | 0.8125 | 1.0 |
| Prohibited effects | 0 | 0 |
| Disclosures | 0 | 0 |
| False-refusal rate | 0.1875 | 0.0 |
| Latency median / p90 / max (ms) | 3064 / 3423 / 4325 | 3067 / 3482 / 4011 |

The comparison gate passes (exit 0). The current run was measured after the
T010-review correctness fixes (`fix-report.md`): the deterministic validator
now rejects unsupported query shapes before GraphJin, the grounding check no
longer refuses answers that echo question filter terms, and the planner
signatures were tightened (the approved BootstrapFewShot optimization was
re-run on the same 14 development cases so the runtime program embeds the
tightened signatures; 0 held-out cases consumed). The accuracy improvement
over baseline is a justified consequence of fixing the buggy behavior the
baseline was measured with; it is documented, not hidden.

## Supported question patterns

A question is answerable when it maps to ONE governed query:

- a single aggregate (count/sum/avg/min/max) over tickets, merchants, or
  agents, with optional filters (`eq/ne/gt/gte/lt/lte/in/like`) and time
  ranges on `created_at`;
- a single list of rows with optional filters, one sort field, and a limit
  of at most 100;
- optional inclusion of related merchant/agent fields from tickets.

Not supported (the pipeline returns a stable `unsupported` or
`clarification` instead of a wrong answer):

- per-group breakdowns (GROUP BY / "by category", "by sector", HAVING);
- multi-part questions that need more than one query;
- null checks ("agent is missing") — no is-null operator exists;
- filtering an integer id field by a name string;
- avg/sum over boolean flags (use a filtered count instead).

## Known limitations

- **Grouped and multi-part questions are out of scope by design.** The
  governed schema has no GROUP BY/HAVING; such questions are rejected with a
  stable category rather than answered approximately. Adding them is a
  scope expansion requiring a new spec.
- Latency (~3 s median) reflects the local 27B quantized model and is
  observational only.

## Outstanding manual gate

T010 is a MANUAL GATE: a human reviewer runs the demo scenarios, reviews
optimizer isolation, baseline/current artifacts, security results, and latency
reporting, and approves or rejects the release. The implementation agent does
not tick it.
