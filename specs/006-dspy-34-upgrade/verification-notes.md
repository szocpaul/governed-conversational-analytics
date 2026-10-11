# Verification Notes: DSPy 3.4 Upgrade (feature 006)

Running log of evidence collected during implementation. Task IDs refer to
`tasks.md`.

## T001 — Pre-change state (2026-10-11)

### Git

```text
$ git log --oneline -3
236a23c Docs: record Tailscale demo-UI access note in AGENTS.md (runtime info for agents)
768df7a Feature 005: Analytics Surface v2 - GROUP BY/having, is-null, ratio metrics (T001-T021 complete, MANUAL GATE approved)
09ade41 Docs: update AGENTS.md (project v1 status) and README.md (post-fix metrics, port 8001, 005 sketch)
```

```text
$ git status
On branch main
Your branch is up to date with 'origin/main'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	specs/006-dspy-34-upgrade/
	specs/006-dspy-upgrade-sketch.md
	specs/007-dspy-34-feature-evaluation-sketch.md

nothing added to commit but untracked files present (use "git add" to track)
```

Working tree: clean except untracked `specs/006-dspy-34-upgrade/`,
`specs/006-dspy-upgrade-sketch.md`, `specs/007-dspy-34-feature-evaluation-sketch.md`.

### requirements.txt (pre-change)

```text
# Conversational query pipeline (feature 002) — pinned versions.
dspy==3.2.1
fastapi==0.143.0
uvicorn[standard]==0.45.0
pydantic==2.12.5
httpx==0.28.1
pytest==9.0.3
python-dotenv
```

### Host interpreter

```text
$ python3 --version
Python 3.14.4
```

```text
$ python3 -m site
sys.path = [
    '/home/ubuntu/governed-conversational-analytics',
    '/usr/lib/python314.zip',
    '/usr/lib/python3.14',
    '/usr/lib/python3.14/lib-dynload',
    '/usr/local/lib/python3.14/dist-packages',
    '/usr/lib/python3/dist-packages',
    '/usr/lib/python3.14/dist-packages',
]
USER_BASE: '/home/ubuntu/.local' (exists)
USER_SITE: '/home/ubuntu/.local/lib/python3.14/site-packages' (doesn't exist)
ENABLE_USER_SITE: True
```

`import dspy` on the live interpreter: `ModuleNotFoundError: No module named 'dspy'`

Note (per tasks.md T001): feature 005 ran on Python 3.12, which no longer
exists on this host (`python3.12` binary gone; the 3.12 user-site is not
importable from 3.14). The live interpreter is Python 3.14.4 and the pinned
stack (including `dspy==3.4.0`) must be installed into the 3.14 user-site
(`python3 -m pip install --user ...`) before any measured run.

## T003 — Install on host interpreter (2026-10-11)

Command: `python3 -m pip install --user --break-system-packages -r requirements.txt`

Note on the flag: the host Python 3.14 is a PEP 668 externally-managed
environment (`/usr/lib/python3.14/EXTERNALLY-MANAGED` present), which blocks
even `--user` installs without `--break-system-packages`. With `--user`, pip
writes only to `~/.local/lib/python3.14/site-packages` (the same user-site
pattern feature 005 used on Python 3.12); no system files are touched. This
is the launch-instructed install path (`python3 -m pip install --user ...`)
made executable on this host.

Result: exit 0. Installed `dspy-3.4.0` plus transitive deps (litellm 1.105.0,
openai 2.54.0, gepa 0.1.4, etc.) and the pinned project deps
(fastapi 0.143.0, uvicorn 0.45.0, pydantic 2.12.5, httpx 0.28.1,
pytest 9.0.3, python-dotenv 1.2.4).

Import verification:

```text
$ python3 -c "import dspy, fastapi, uvicorn, pydantic, httpx, pytest, dotenv; print(dspy.__version__)"
3.4.0
```

All pinned dependencies import on Python 3.14.4. No pin changes beyond
`dspy==3.2.1 -> 3.4.0` were required (FR-001).

Stack check (pre-measurement): PostgreSQL container `itsm-foundation-postgres-1`
healthy on 127.0.0.1:5432; GraphJin container `itsm-foundation-graphjin-1`
serving on 127.0.0.1:8081 — verified with a real governed query
(`{ tickets(limit: 1) { ticket_id priority } }` → 200 with data). Note: the
GraphJin container restarted during this session (crash-loop recovery observed
in logs at 16:46Z); it is healthy and serving the governed schema.

## T004 — LLM preflight on DSPy 3.4.0 (2026-10-11)

Command: `python3 -m app.ai.preflight` (env loaded from `.env` via
python-dotenv into the process environment; `source .env` in bash mangles the
backslash in the pinned model ID, so env is loaded with `load_dotenv`).

First run failed with `LLM_BASE_URL is not configured` (`.env` not exported
into the shell) — an environment-setup issue, not an endpoint failure. After
loading `.env` correctly, preflight exited 0.

`artifacts/llm-preflight.json` records:
- exact API model ID: `models\Qwen3.8-27B-UD-Q4_K_M.gguf` (unchanged — no
  provider/model switch, FR-002);
- deterministic smoke chat completion: ok (reply `ready`);
- typed DSPy prediction: ok;
- `dspy_version`: `3.4.0`.

Scope note: preflight.py did not record the DSPy version, which T004 requires
in the artifact. Added a single `dspy_version` field to the preflight record
(minimal metadata addition, in-scope for artifacts) with a failing test first
(`tests/unit/test_preflight.py`), then the one-line change.

## T005 — Full test suite on DSPy 3.4.0 (2026-10-11)

Command: `python3 -m pytest -q`

First run failed at collection: `ModuleNotFoundError: No module named
'psycopg'` in 8 integration/security test modules. `psycopg` is a test-only
dependency introduced by feature 001 (not in requirements.txt; feature 001
runner report pins psycopg 3.3.6 + psycopg-binary 3.3.6, installed with
`uv pip ... "psycopg[binary]"`). Installed the same pin into the 3.14
user-site: `python3 -m pip install --user --break-system-packages
"psycopg[binary]==3.3.6"` (exit 0). No requirements.txt change — psycopg is
not a runtime dependency of the query path.

Result: **396 passed, 1 warning in 129.77s**. Exit 0.

The single warning is `StarletteDeprecationWarning` from
`fastapi/testclient.py` (httpx testclient deprecation) — a third-party
(FastAPI/Starlette) warning in test tooling, NOT a DSPy deprecation warning;
tracked under T006/T007 findings.

## T006 — Deprecation-surface detection (2026-10-11)

Command: `python3 -W default::DeprecationWarning -m pytest -q` (full output
captured; warnings summary inspected).

Result: exit 0, 396 passed. **Zero DSPy deprecation warnings.** Exactly one
warning total:

```text
.../fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with
`starlette.testclient` is deprecated; install `httpx2` instead.
```

Finding classification: this is a **Starlette** (third-party test-tooling)
deprecation warning, raised at `import fastapi.testclient` inside the
installed `fastapi` package — NOT a DSPy deprecation warning, and not raised
from any project callsite. FR-004/T006/T007 scope is the DSPy legacy-LM
deprecation surface (spec US1: "zero DSPy deprecation warnings in measured
runs"; T007 stop-and-report clause is explicitly about "a warning [that]
originates inside DSPy itself"). There is no application-side callsite fix
for a warning emitted inside fastapi's own testclient module, and a warning
filter is a prohibited workaround (T007).

DSPy LM-path probe: `python3 -W default::DeprecationWarning -m
app.ai.preflight` (exercises `configure_dspy` + `dspy.Predict` against the
pinned endpoint) exited 0 with **zero warnings of any kind** — the project's
LM construction in `app/ai/llm.py` (standard `dspy.LM("openai/<id>",
api_base=..., model_type="chat")`) is on the canonical 3.4 path and emits no
deprecation warning.

## T007 — Deprecation-warning elimination (2026-10-11)

No DSPy deprecation warnings exist to eliminate (T006 found zero). No change
to `app/ai/llm.py` was required (research.md D3: the standard LiteLLM-style
configuration is the canonical 3.4 pattern; no speculative engine parameter
added). The lone Starlette testclient warning is out of DSPy scope per the
classification above; it will be re-confirmed as the only non-DSPy warning in
the measured runs (T011/T012), which must show zero DSPy warnings to be
valid.

## T008/T009 — Preservation of pre-upgrade evidence (2026-10-11)

Failing test written first (`tests/unit/test_artifact_preservation.py`),
failure observed (no `*-pre-006-*` copies existed). Copies created with
`cp`-equivalent (`shutil.copyfile`) and verified byte-identical via SHA-256.

Naming: data-model.md places each preserved copy next to its source
(`app/ai/optimized_program-pre-006-*.json` beside `app/ai/optimized_program.json`;
the three artifacts under `artifacts/`). Date stamp: 2026-10-11.

| Source | Copy | SHA-256 (both) |
|---|---|---|
| artifacts/baseline.json | artifacts/baseline-pre-006-2026-10-11.json | d58702e8a180616c0047f05ee1ec053ba522b8ef36ae80be3d0a6bc1429bb24b |
| artifacts/current.json | artifacts/current-pre-006-2026-10-11.json | bfddd856f583be9d1103693b361552cb1198e3f01f31e96492086b186791f798 |
| artifacts/optimization-run.json | artifacts/optimization-run-pre-006-2026-10-11.json | a829bafc184e5c8fa5284d72ec7b7270a09a5b99e309fd391163bc5ed2ac4448 |
| app/ai/optimized_program.json | app/ai/optimized_program-pre-006-2026-10-11.json | 421b664260b97ac9df3516111a28e7591ae2971d1207c285077dbe673e91f235 |

Test passes: 1 passed. These four `*-pre-006-*` files are IMMUTABLE from this
point; no later task may modify them.

## T010 — Measured-run discipline + metadata (2026-10-11)

Verified in `evaluation/run.py`:
- `--cache=true` exits 2 (measured runs must disable the response cache);
- the runner forces `LLM_TEMPERATURE=0` and `LLM_CACHE=false` for measured
  runs regardless of ambient env;
- `.env` has `LLM_TEMPERATURE=0`, `LLM_CACHE=false`.

Metadata gap found: `collect_metadata` did not record the DSPy or Python
version, which T010/contract require in the baseline metadata. Minimal
in-scope extension: added `dspy_version` and `python_version` to
`collect_metadata` (tests first: `tests/evaluation/test_run_metadata.py`
failed with KeyError, then passed; existing `test_regression_gate.py`
metadata tests still pass — 14 passed).

Noise-sampling procedure (feature 004/005 discipline): the runner has no
case-selection flag, so the representative 8-case sample (same IDs as feature
005: EVAL-001, EVAL-004, EVAL-017, EVAL-018, EVAL-019, EVAL-020, EVAL-021,
EVAL-022 — covering count, filtered_count, grouped, is-null, ratio) is run
via a temporary cases file passed to `--cases`, 3 repetitions, then the full
33-case held-out run. The noise block is merged into the baseline artifact.

## T011 — Re-baseline on DSPy 3.4.0 (2026-10-11)

**Critical measurement-validity decision**: the first noise-run attempt loaded
the stale 3.2.1-compiled `app/ai/optimized_program.json` (DSPy logged
`WARNING dspy.primitives.base_module: mismatch of python/dspy version between
saved model and current environment`). That run is INVALID as baseline
evidence — baseline discipline (feature 004: pre-optimization baseline;
feature 005 runner report decision #1) measures the BASE program with the
optimized artifact moved aside. Corrected: moved the stale 3.2.1 artifact out
of the loader path (to /tmp/006-staging/; the byte-identical preserved copy
`app/ai/optimized_program-pre-006-2026-10-11.json` remains intact and its
SHA-256 is unchanged), then re-ran. T012 recompiles a fresh 3.4.0 artifact.

Noise sample (base program, `--cases /tmp/noise-sample-cases.json`,
`-W default::DeprecationWarning`), 3 repetitions of the 8-case representative
sample (EVAL-001/004/017/018/019/020/021/022):
- accuracy values: [1.0, 1.0, 1.0] (zero variance)
- structural validity values: [1.0, 1.0, 1.0] (zero variance)
- latency medians: [3492.43, 3358.4, 3361.45] ms
- zero DSPy deprecation warnings in all three runs (only the known Starlette
  testclient warning).

Full held-out run: `python3 -W default::DeprecationWarning -m evaluation.run
--cache=false --output artifacts/baseline.json` — exit 0, 33 cases
(11 security):
- structural_validity: 1.0
- execution_accuracy: 1.0
- prohibited_effects: 0
- disclosures: 0
- false_refusals: 0 (rate 0.0)
- latency: median 3077.86 ms, p90 4058.94 ms, min 970.31 ms, max 4181.04 ms
- zero DSPy deprecation warnings.

`artifacts/baseline.json` metadata: `dspy_version: 3.4.0`,
`python_version: 3.14.4`, `optimizer.type: none` (base program),
`temperature: 0.0`, `cache: false`, model ID
`models\Qwen3.8-27B-UD-Q4_K_M.gguf`, noise block merged (feature 005
convention).

## T012 — Approved BootstrapFewShot re-optimization on 3.4.0 (2026-10-11)

Command: `python3 -W default::DeprecationWarning -m app.ai.optimization`
— exit 0, zero warnings of any kind (no DSPy deprecation warnings).

`artifacts/optimization-run.json` verifies:
- optimizer: `dspy.BootstrapFewShot`, config unchanged (metric_threshold 1.0,
  max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors 3);
- input_case_ids: 20 dev cases (DEV-001..DEV-020) — dev only;
- `held_out_ids_consumed`: 0;
- accepted_demo_ids: [DEV-004, DEV-005, DEV-009, DEV-010, DEV-016, DEV-019,
  DEV-020] — all ⊆ dev IDs (isolation assertion in the runner passed);
- output_program_sha256:
  3769c4821d9987787b3e388dfe7c77ccc5f3e81ba859944e0475e0375e2bdafe;
- versions.dspy: "3.4.0", model_id pinned, temperature 0.0, cache false;
- errors: [].

Expected cross-version difference (spec Background): the 3.2.1 run accepted 4
demos (DEV-004/005/019/020); the 3.4.0 run accepts 7. BootstrapFewShot
received bugfixes in 3.4, so a different accepted demonstration set is
expected and is handled by re-optimization (not by reusing the old artifact).

## T013 — Optimized-program load verification (2026-10-11)

New test `tests/unit/test_program_loading.py`: constructs `QueryProgram` and
calls `.load()` on the newly compiled `app/ai/optimized_program.json`,
asserting the loaded `plan` predictor carries demonstrations. This guards the
silent-fallback risk in `app/api/routes.py` (`_make_query_program` swallows
load exceptions and falls back to the base program — a stale/incompatible
artifact would silently degrade quality, research.md D4).

Result: 1 passed. The 3.4.0-compiled artifact loads cleanly on DSPy 3.4.0
with demonstrations present (no python/dspy version-mismatch warnings, unlike
the stale 3.2.1 artifact in the first invalid noise attempt).

## T014 — Post-optimization held-out evaluation + compare gate (2026-10-11)

Commands:
- `python3 -m evaluation.run --cache=false --output artifacts/current.json`
  — exit 0, 33 cases (11 security): structural_validity 1.0,
  execution_accuracy 1.0, prohibited_effects 0, disclosures 0,
  false_refusals 0; latency median 3034.69 ms, p90 3645.99 ms, min 946.33 ms,
  max 4081.47 ms. Zero DSPy deprecation warnings (only the known Starlette
  testclient warning).
- `python3 -m evaluation.compare --baseline artifacts/baseline.json
  --current artifacts/current.json` — **exit 0**, reasons: [] (no failed P1
  thresholds, no execution-accuracy degradation > 5pp — both are 1.0, no
  prohibited effect, no unauthorized disclosure).

`artifacts/current.json` metadata records `optimizer.type:
BootstrapFewShot` with the new program SHA-256
3769c4821d9987787b3e388dfe7c77ccc5f3e81ba859944e0475e0375e2bdafe.

## T015/T016 — Cross-version quality report (2026-10-11)

Failing tests written first (`tests/evaluation/test_cross_version_report.py`,
2 tests: per-version metric coverage + no-verdict invariant; version fallback
for pre-upgrade artifacts that predate the `dspy_version` metadata field).
Failure observed (module did not exist), then implemented
`evaluation/cross_version_report.py` as a separate small script with a
`__main__` entry (research.md D6: `evaluation/compare.py` keeps its clean
same-version gate semantics). Tests pass: 2 passed.

Generated `artifacts/cross-version-006.json` comparing the post-optimization
held-out results of both versions:

| metric | 3.2.1 (preserved) | 3.4.0 (new) |
|---|---|---|
| structural_validity | 1.0 | 1.0 |
| execution_accuracy | 1.0 | 1.0 |
| prohibited_effects | 0 | 0 |
| disclosures | 0 | 0 |
| false_refusals | 0 | 0 |
| latency median (ms) | 2923.81 | 3034.69 |
| latency p90 (ms) | 3350.27 | 3645.99 |
| latency max (ms) | 3848.72 | 4081.47 |

Quality delta: none (identical validity/accuracy/security). Latency is
observational only (never gated): 3.4.0 is modestly slower on median/p90/max
(~4-9%), reported as human review input. The report contains NO pass/fail
verdict field (FR-009).

Artifact SHA-256 recorded for both: 3.2.1 current-pre-006
bfddd856f583be9d1103693b361552cb1198e3f01f31e96492086b186791f798; 3.4.0
current a7afcfe32873e89f2289ea8711c1a235b83f88e847c23c09dcc3f40d740dd62e.

## T017 — Docs (2026-10-11)

- `README.md`: added feature 006 to the feature list; updated the evaluation
  results section to the 3.4.0 state (validity 1.0, accuracy 1.0, zero
  security issues, latency median ~3.0 s / p90 ~3.6 s observational);
  documented the preserved `*-pre-006-*` artifacts and the cross-version
  report; added `evaluation/cross_version_report.py` and the 006 spec dir to
  the repository layout. No private endpoint in any doc.
- `AGENTS.md`: project status updated — feature 006 implemented (T001-T018),
  awaiting the T019 MANUAL GATE; DSPy 3.4.0 on Python 3.14.4; new
  baseline/optimization artifacts recorded.
