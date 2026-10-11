# Runner Report: DSPy 3.4 Upgrade with Re-Baseline and Re-Optimization

**Feature**: `specs/006-dspy-34-upgrade/` (approved 2026-10-11)
**Runner**: autonomous Prime Agent worker (spec006), 2026-10-11
**Git HEAD at launch**: `236a23c` (clean except untracked `specs/006*`, `specs/007*`)

## Outcome

**T001-T018 COMPLETE. T019 (MANUAL GATE) left unchecked for human review.**
The pinned DSPy dependency is upgraded from 3.2.1 to 3.4.0 on Python 3.14.4;
the full test suite passes (401 passed), measured runs show zero DSPy
deprecation warnings, a new 3.4.0 baseline and re-optimized program are
recorded under feature 004 discipline, the same-version comparison gate
passes (exit 0), and the cross-version report shows no quality delta versus
3.2.1.

## 1. Completed task IDs

T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011, T012,
T013, T014, T015, T016, T017, T018.

## 2. Incomplete / blocked task IDs

None. T019 (MANUAL GATE) is intentionally unchecked — human review required.

## 3. Files changed

Code / config:
- `requirements.txt` — `dspy==3.2.1` → `dspy==3.4.0` (only pin change).
- `app/ai/preflight.py` — added `dspy_version` to the preflight record
  (T004 metadata requirement).
- `evaluation/run.py` — `collect_metadata` now records `dspy_version` and
  `python_version` (T010 metadata requirement).
- `evaluation/cross_version_report.py` — NEW: cross-version report generator
  (T016; never gated).
- `app/ai/optimized_program.json` — recompiled on DSPy 3.4.0 (T012).

Tests (all new, failing-first where behavior changed):
- `tests/unit/test_preflight.py` (T004), `tests/unit/test_artifact_preservation.py`
  (T008/T009), `tests/unit/test_program_loading.py` (T013),
  `tests/evaluation/test_run_metadata.py` (T010),
  `tests/evaluation/test_cross_version_report.py` (T015).

Docs:
- `README.md` — feature 006 entry, results, artifact inventory, layout.
- `AGENTS.md` — project status (feature 006 implemented, awaiting T019).

Artifacts:
- Regenerated: `artifacts/llm-preflight.json`, `artifacts/baseline.json`,
  `artifacts/current.json`, `artifacts/optimization-run.json`.
- Preserved (immutable, byte-identical to pre-upgrade sources):
  `artifacts/baseline-pre-006-2026-10-11.json`,
  `artifacts/current-pre-006-2026-10-11.json`,
  `artifacts/optimization-run-pre-006-2026-10-11.json`,
  `app/ai/optimized_program-pre-006-2026-10-11.json`.
- New: `artifacts/cross-version-006.json`.

Spec artifacts: `specs/006-dspy-34-upgrade/verification-notes.md` (new),
`specs/006-dspy-34-upgrade/runner-report.md` (this file),
`specs/006-dspy-34-upgrade/tasks.md` (T001-T018 marked).

## 4. Commits created

None by this runner (no commit was requested; changes are in the working
tree for human review at the manual gate).

## 5. Pinned dependency versions

- `dspy==3.4.0` (upgraded from 3.2.1 — the only pin change, FR-001)
- `fastapi==0.143.0`, `uvicorn[standard]==0.45.0`, `pydantic==2.12.5`,
  `httpx==0.28.1`, `pytest==9.0.3`, `python-dotenv` (unchanged)
- Test-only: `psycopg[binary]==3.3.6` (feature 001 pin, reinstalled into the
  Python 3.14 user-site; not a runtime dependency, not in requirements.txt)
- Key transitive (installed by pip): litellm 1.105.0, openai 2.54.0,
  pydantic-core 2.41.5, starlette 1.7.0

## 6. Dataset commit SHA, license, checksums

Unchanged by this feature (no dataset work). Pinned source:
`github.com/drapertoby/itsm-ticket-dataset` @ commit
`cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`, MIT License; checksums in
`artifacts/import-manifest.json` (unchanged — only the `imported_at`
timestamp was refreshed by the test suite's import-path test; row counts and
SHA-256 checksums are intact).

## 7. API model ID and runtime

- Exact API model ID: `models\Qwen3.8-27B-UD-Q4_K_M.gguf` (unchanged — no
  provider/model switch, FR-002). Verified by preflight on 3.4.0.
- DSPy version: 3.4.0. Python: 3.14.4 (`/usr/bin/python3`). LLM runtime:
  llama.cpp (local OpenAI-compatible endpoint; URL never exposed).

## 8. Validation commands and results

| Command | Result |
|---|---|
| `python3 -m pytest -q` | exit 0 — **401 passed**, 1 warning |
| `python3 -W default::DeprecationWarning -m pytest -q` | exit 0 — 396 passed (pre-new-tests), **zero DSPy deprecation warnings** |
| `python3 -m app.ai.preflight` | exit 0 — model ID verified, smoke + typed prediction OK, `dspy_version: 3.4.0` |
| `python3 -W default::DeprecationWarning -m evaluation.run --cache=false --output artifacts/baseline.json` | exit 0 — 33 cases, zero DSPy deprecation warnings |
| `python3 -W default::DeprecationWarning -m app.ai.optimization` | exit 0 — 20 dev examples, zero warnings |
| `python3 -m evaluation.run --cache=false --output artifacts/current.json` | exit 0 — 33 cases |
| `python3 -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json` | **exit 0** — reasons: [] |

The single warning in test runs is `StarletteDeprecationWarning` from
`fastapi/testclient.py` (third-party test-tooling deprecation, emitted inside
the installed `fastapi` package, not a DSPy warning and not from any project
callsite). FR-004/T006/T007 scope is the DSPy legacy-LM deprecation surface;
there is no application-side fix and a warning filter is a prohibited
workaround (T007). All measured runs show **zero DSPy deprecation warnings**.

## 9. Baseline and current metrics (DSPy 3.4.0)

| Metric | Baseline (base program) | Current (optimized) |
|---|---|---|
| structural_validity | 1.0 | 1.0 |
| execution_accuracy | 1.0 | 1.0 |
| prohibited_effects | 0 | 0 |
| disclosures | 0 | 0 |
| false_refusals | 0 | 0 |
| total / security cases | 33 / 11 | 33 / 11 |

Baseline noise block: 3 × 8-case representative sample (EVAL-001/004/017/018/
019/020/021/022), accuracy [1.0, 1.0, 1.0] and validity [1.0, 1.0, 1.0] —
zero variance. Baseline metadata records `dspy_version: 3.4.0`,
`python_version: 3.14.4`, `optimizer.type: none`, temperature 0, cache false.

## 10. Security-effect and disclosure results

Zero prohibited database effects and zero unauthorized disclosures across all
33 held-out cases (11 security) in both the baseline and the post-optimization
run; the comparison gate confirms zero. The full security test suite
(`tests/security/`) passes under the 401-test run.

## 11. Latency (observational only — never gated)

| | Baseline (3.4.0) | Current (3.4.0) | 3.2.1 (preserved, for context) |
|---|---|---|---|
| median | 3077.86 ms | 3034.69 ms | 2923.81 ms |
| p90 | 4058.94 ms | 3645.99 ms | 3350.27 ms |
| max | 4181.04 ms | 4081.47 ms | 3848.72 ms |

Per-request values are in `artifacts/baseline.json`, `artifacts/current.json`,
and `artifacts/cross-version-006.json`. Latency alone does not gate.

## 12. Known limitations

- The Starlette `testclient` deprecation warning (third-party, test tooling)
  appears in test/measured output; it is not a DSPy warning and has no
  application-side fix (a filter is prohibited). It does not affect the query
  path.
- `artifacts/import-manifest.json`'s `imported_at` timestamp is refreshed by
  the test suite's import-path test (`tests/integration/test_database_import.py`);
  dataset content, checksums, and row counts are unchanged.
- The accepted demonstration set changed between 3.2.1 (4 demos) and 3.4.0
  (7 demos) — expected per spec (BootstrapFewShot 3.4 bugfixes); handled by
  re-optimization, not by reusing the old artifact.
- Cross-version latency is modestly higher on 3.4.0 (median ~+4%, p90 ~+9%);
  observational only, reported as human review input.

## 13. Outstanding manual gates

- **T019 MANUAL GATE** — human reviewer reviews this report, the cross-version
  report (`artifacts/cross-version-006.json`), the preserved-artifact
  checksums (`verification-notes.md` T009), the deprecation-warning evidence
  (T006/T007), and the eval-set isolation proof (`optimization-run.json`:
  `held_out_ids_consumed == 0`, accepted demos ⊆ dev IDs), and approves or
  rejects the release. A quality regression versus 3.2.1 would be a human
  decision point (FR-009) — none was observed (identical validity/accuracy/
  security).

## Decisions and assumptions (reported per harness rules)

1. **PEP 668 install path**: the host Python 3.14 is externally-managed, which
   blocks even `--user` pip installs without `--break-system-packages`. Used
   `python3 -m pip install --user --break-system-packages` — with `--user`,
   pip writes only to `~/.local/lib/python3.14/site-packages` (the same
   user-site pattern feature 005 used on 3.12); no system files touched. This
   is the launch-instructed install path made executable on this host.
2. **Stale 3.2.1 optimized program moved aside before baseline** (feature 005
   precedent): the first noise-run attempt loaded the stale artifact (DSPy
   logged a python/dspy version-mismatch WARNING) and was discarded as invalid
   baseline evidence. The artifact was moved out of the loader path; the
   byte-identical preserved copy is intact. T012 recompiled a fresh 3.4.0
   artifact.
3. **Preservation-test invariant corrected**: the T008 test initially asserted
   source==copy byte-identity, which is only true at preservation time. After
   re-measurement the live sources legitimately differ. The permanent invariant
   is immutability of the preserved copies; the test now asserts their SHA-256
   match the values recorded at T009.
4. **Metadata additions (in-scope)**: `dspy_version` added to the preflight
   record (T004) and `dspy_version`/`python_version` to `collect_metadata`
   (T010) — both required by the contract and absent from the existing code.
5. **Cross-version report compares post-optimization results** of both
   versions (`current-pre-006` vs `current.json`) — the like-for-like
   optimized-program comparison that is the human decision input (FR-009).
