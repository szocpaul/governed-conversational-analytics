# Phase 0 Research: Synthetic Ticket Texts

**Feature**: 009-synthetic-ticket-texts | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

All design unknowns from the plan's Technical Context are resolved below.
Each entry: Decision / Rationale / Alternatives considered. Grounding:
`app/ai/llm.py` (pinned-endpoint discipline), `app/ai/signatures.py`
(idiomatic typed DSPy), `scripts/import_dataset.py` (atomic import),
feature-001 tests (manifest expectations), DSPy 3.4.0 structured-output
behavior.

## R1 — DSPy typed signature design for batch JSON output

**Decision**: One signature, one batch in, one typed batch out.

```python
class TicketTextEntry(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    ticket_id: int
    short_description: str
    description: str
    resolution_notes: str | None   # required to be null for open tickets

class GenerateTicketTexts(dspy.Signature):
    """(docstring = instruction; versioned via PROMPT_VERSION constant)"""

    tickets_json: str = dspy.InputField(
        desc="JSON array of ticket context objects (category, sub_category, "
             "priority, sla flags, resolution time, reopened, open/closed, ...)")
    entries: list[TicketTextEntry] = dspy.OutputField(
        desc="one entry per input ticket, same order, same ticket_ids")
```

The instruction docstring (the "prompt asset") lives in the signature
itself — the house discipline from `app/ai/signatures.py` is "no hard-coded
prompt strings outside DSPy signatures". A module-level `PROMPT_VERSION`
constant (e.g. `"1"`) is bumped on any docstring/field-description change
and recorded in the manifest; this replaces the template-version concept
from the original sketch. Prompt input is a compact JSON array of the
tickets' structured columns only (never free text, never credentials).

**Rationale**: A single typed call per batch keeps the model contract
explicit and machine-checkable; pydantic-typed output fields make DSPy emit
and parse strict JSON instead of prose; a per-entry model makes
zero-tolerance validation natural (schema + ticket_id set equality +
per-field rules). `resolution_notes` is modeled as required-but-nullable so
the model must explicitly emit `null` for open tickets instead of omitting
the key (omission would be ambiguous).

**Alternatives considered**: (a) One model call per ticket — rejected:
~2057 calls, 5x the latency and cost for no quality gain; human approved
batching. (b) Free-text output parsed by regex — rejected: fragile,
untyped, contradicts the typed-DSPy discipline. (c) External prompt
template files under `data/templates/` — rejected: the human revision
decision replaced templates with DSPy signatures; an extra prompt-file
layer would duplicate the source of truth.

## R2 — Batch size 5 rationale

**Decision**: 5 tickets per model call (human-approved), giving 412 calls
for 2057 tickets (411 x 5 + 1 x 2). `--batch-size` is a CLI flag defaulting
to 5; the value actually used is recorded in the manifest (`batch_config`).

**Rationale**: 5 balances (a) blast radius — a malformed response costs at
most a 5-ticket retry; (b) output length — 5 entries x ~120 words stays
well inside the model's reliable JSON generation range, reducing truncation
risk; (c) throughput — 5x fewer calls than per-ticket generation. The exact
number was approved by the human; the plan only makes it configurable and
recorded.

**Alternatives considered**: 1/call (too slow), 10-20/call (higher
truncation and ordering-error risk, larger retry blast radius), dynamic
sizing (needless complexity for a one-time offline run).

## R3 — Checkpoint format and resume semantics

**Decision**: Append-only JSONL checkpoint at
`artifacts/tickets_texts.checkpoint.jsonl`. After each accepted batch the
CLI appends one line per entry:
`{"ticket_id": int, "short_description": str, "description": str,
"resolution_notes": str|null}` and flushes to disk. On startup the CLI
loads the checkpoint (if any), treats its ticket_ids as done, and continues
with the remaining batches in deterministic ticket order (tickets.csv
order). Resume is the default when a checkpoint exists; `--fresh` discards
it explicitly. The final artifact `data/raw/tickets_texts.jsonl` is written
only after all 2057 entries are accepted, then the checkpoint file is
deleted. A checkpoint whose entries disagree with the pinned tickets.csv
(unknown ticket_id) fails the run loudly.

**Rationale**: Append-only JSONL is crash-safe (a torn final line is
detectable and fails loudly on load), human-auditable, diff-friendly, and
needs no extra dependencies. Writing the final artifact only at completion
keeps the "pinned artifact" boundary crisp: a half-finished run leaves only
a clearly-named transient checkpoint, never a partial artifact.
Ticket-order batching makes progress deterministic and the manifest's row
order stable.

**Alternatives considered**: (a) Single JSON checkpoint rewritten each
batch — rejected: rewrite is not crash-atomic without extra fsync/rename
machinery. (b) SQLite offset store — rejected: dependency and opaque state
for zero benefit at 2057 rows. (c) Offset-only checkpoint (just a counter)
— rejected: loses the accepted entries, so a crash would force regenerating
them and would make "resume must not silently skip" unverifiable.

## R4 — Strict output validation strategy (DSPy JSONAdapter + bounded retry)

**Decision**: The generation program runs `dspy.Predict(GenerateTicketTexts)`
under an explicitly configured `dspy.JSONAdapter()` so typed pydantic output
is requested as strict JSON. Per batch, acceptance requires ALL of:
(1) adapter/pydantic parse succeeds; (2) the entry set's ticket_ids equal
the batch's input ticket_ids exactly (no missing, no extra, no duplicates);
(3) per-entry rules: non-empty strings, resolution_notes null iff the
ticket is open, hard length limits (see R5). On any failure the batch is
retried up to `--max-retries` (default 2) with the identical request; after
that the CLI exits non-zero naming the failing batch. No repair, no
fabrication, no skipping.

**Rationale**: JSONAdapter + pydantic gives schema-level strictness for
free; the ticket_id equality check catches ordering/hallucination errors
that schema validation cannot; identical-request retries are appropriate at
temperature 0 for transient truncation/parse issues while remaining
auditable (every retry is logged to stderr and counted in the manifest).

**Alternatives considered**: (a) `dspy.Refine`/`dspy.Retry` wrappers —
rejected: they add opaque retry machinery and reward-based logic meant for
quality optimization, not for a strict accept/reject gate; a plain bounded
loop is smaller and fully auditable. (b) ChatAdapter with manual JSON
extraction — rejected: weaker guarantee, more parsing code. (c) Single
full-corpus call — rejected: violates the approved batching.

## R5 — Deterministic validation-suite design (offline, no model)

**Decision**: `scripts/validate_ticket_texts.py` validates a generated
artifact against the pinned tickets.csv. All checks are deterministic,
documented, and pass/fail (no warnings-as-pass). The suite runs both as a
CLI gate before human review and as unit tests. Checks:

1. **Schema/coverage**: every line parses as the entry schema; ticket_ids
   are exactly the 2057 pinned ids, each once.
2. **Non-empty fields**: no empty/whitespace strings; no unresolved-slot
   artifacts (defense-in-depth: reject `{...}`-style markers and template
   braces even though generation is prompt-based).
3. **Length limits** (spec-authorized tightening, spec Assumptions):
   short_description = exactly 1 sentence and <= 100 chars (prompt targets
   ~80); description = 2-4 sentences and <= 600 chars; resolution_notes =
   1-3 sentences and <= 450 chars when present. Sentence counting:
   deterministic regex split on `[.!?]+` followed by whitespace/end —
   documented as a convention the generator prompt is aligned to (plain
   sentences, no abbreviations with periods).
4. **English-only**: deterministic heuristic — >= 95% ASCII printable
   characters per field AND at least one common English function word
   (the/a/and/is/to/...) per sentence. Documented as a heuristic gate, not
   a language classifier; it deterministically catches non-English output
   and mojibake.
5. **Secrets/PII scan**: reject strings matching credential patterns
   (password=, bearer tokens, API-key shapes, PEM headers, e-mail
   addresses, phone-number shapes, IPv4 addresses). Patterns are fixed in
   the validator and unit-tested with canary strings.
6. **Category consistency**: a hand-maintained, versioned lexicon in the
   validator maps each of the 20 sub_categories to required-topic keywords
   (>= 1 must appear in short_description+description, case-insensitive)
   and each *other* category to exclusive-conflict keywords that must NOT
   appear (e.g. "login"/"password" on a Payments ticket fails). The lexicon
   is deterministic, reviewed like code, and small (20 pairs). It checks
   consistency, not literary quality — deep quality review is the human
   MANUAL GATE.
7. **NULL rule**: resolution_notes is null exactly for the 250 tickets with
   empty closed_at in tickets.csv, and non-null for the other 1807.

**Rationale**: Every check is implementable with stdlib (re, json, csv) —
no new dependencies; deterministic rules are testable and their thresholds
are reviewable constants; splitting "mechanical consistency" (this suite)
from "human judgment" (MANUAL GATE) matches the spec's quality-gate design.

**Alternatives considered**: (a) LLM-as-judge validation — rejected:
non-deterministic, violates the model-free gate. (b) A full NLP library
(langdetect, NLTK sentence tokenizer) — rejected: new dependencies and
model files for marginal gain over documented heuristics at 2057 rows.
(c) Skipping category consistency — rejected: spec FR-011 explicitly
requires it.

## R6 — Schema migration approach (CREATE TABLE + idempotent ALTER)

**Decision**: Extend the `itsm.tickets` CREATE TABLE in `database/schema.sql`
with the three columns (`short_description text`, `description text`,
`resolution_notes text`, all nullable, with a `-- GENERATED (feature 009)`
comment), AND append three idempotent
`ALTER TABLE itsm.tickets ADD COLUMN IF NOT EXISTS ...` statements after the
CREATE TABLE. Fresh setups (and the documented reset path
`reset_database.py` -> `initialize_database.py`) get the columns from the
CREATE TABLE; existing initialized databases get them from the ALTERs on
the next `initialize_database.py` run. No separate migration file, no
in-place data migration (texts arrive via the import script).

**Rationale**: schema.sql is already the single idempotent source of truth
("safe to run multiple times"); keeping the columns in the CREATE TABLE
preserves that, while the ADD COLUMN IF NOT EXISTS lines keep existing
databases convergent without forcing a reset. Nullable columns are correct
because pre-import databases legitimately have no texts yet.

**Alternatives considered**: (a) ALTER-only in a new migration file —
rejected: creates a second schema source of truth and a migration-ordering
problem the project deliberately does not have. (b) Recreate-only (require
reset) — rejected: works, but needlessly destructive for a purely additive
change; the reset path remains the documented clean path regardless.
(c) Separate `itsm.ticket_texts` table — rejected: binding human decision 1
chose additive columns.

## R7 — Atomic + idempotent import of the generated fields

**Decision**: `scripts/import_dataset.py` gains a second phase inside the
SAME single transaction: after the existing pinned-CSV upserts, it loads
`data/raw/tickets_texts.jsonl`, verifies (a) the file's SHA-256 equals
`texts-manifest.json`'s recorded output checksum, (b) ticket_id coverage is
exactly the pinned set, (c) the NULL rule holds against tickets.csv, and
(d) `texts-manifest.json` carries a human-recorded approval marker
(`human_review.approved == true` with reviewer + date) — then upserts the
three columns per ticket (`ON CONFLICT (ticket_id) DO UPDATE` of the three
generated columns only) and re-checks row counts. Any failure rolls back
EVERYTHING (existing behavior: single transaction). Idempotency: upserts
make re-runs converge to the same state; verification is by checksum, so
re-importing the same pinned artifact is a no-op in content. The clean
reset path is untouched.

**Rationale**: Reusing the existing single-transaction import keeps one
atomicity story and one manifest story; checksum-gating the artifact makes
"pinned and human-approved" machine-enforced (the import cannot silently
import a modified or unreviewed artifact).

**Alternatives considered**: (a) Separate import script for texts —
rejected: two transactions would break the "atomic together with
tickets.csv" requirement (FR-010/FR-014). (b) Import without approval
check — rejected: FR-015 requires the human gate to be effective, not
procedural-only.

## R8 — Extending artifacts/import-manifest.json without breaking feature-001 tests

**Decision**: Add ONE new top-level key `generated_texts` written by the
import script:

```json
"generated_texts": {
  "artifact_path": "data/raw/tickets_texts.jsonl",
  "artifact_sha256": "<hex>",
  "texts_manifest_path": "data/raw/texts-manifest.json",
  "texts_manifest_sha256": "<hex>",
  "artifact_version": "1",
  "row_count": 2057,
  "human_review": {"approved": true, "reviewer": "<name>", "reviewed_at": "<iso>"},
  "imported_at": "<iso>"
}
```

Existing keys (`dataset`, `import`, `notes`) are structurally untouched;
the import script updates `import.imported_at` as before.

**Rationale**: Feature-001 tests
(`tests/integration/test_database_import.py`) assert only
`manifest["import"]` presence and `manifest["dataset"]["pinned_commit_sha"]`
— an additive top-level key cannot break them. Mirroring the artifact into
the import manifest satisfies FR-011/FR-012's "referenced from the import
manifest" while `texts-manifest.json` remains the full provenance record.

**Alternatives considered**: Nesting under `import` — rejected: mixes
run-result data with artifact provenance and risks colliding with
feature-001 expectations. Referencing by path only without hashes —
rejected: loses tamper evidence.

## R9 — Artifact format and commit decision (JSONL, committed)

**Decision**: The generated artifact is JSONL (one JSON object per line, in
pinned tickets.csv order) at `data/raw/tickets_texts.jsonl`, COMMITTED to
Git together with `data/raw/texts-manifest.json` once human-approved.
Estimated size ~1.5 MB (2057 x ~700 chars). The transient checkpoint lives
under `artifacts/` and is never committed (deleted on success;
`.gitignore` entry added during implementation).

**Rationale**: JSONL avoids CSV escaping bugs for multi-sentence text with
commas/quotes, matches the checkpoint format (one code path), and streams
line-by-line for validation. Committing matches the project's pinning
discipline: raw CSVs and `artifacts/baseline.json` /
`app/ai/optimized_program.json` are all committed pinned artifacts; tests
can then verify checksums without regeneration, and human review happens on
a real diff. "Raw" in `data/raw/` means "input-side, immutable data", which
the approved artifact is (the spec's key entity "Generation Artifact").

**Alternatives considered**: (a) CSV output (original sketch) — rejected:
escaping fragility for free text. (b) Gitignored artifact, regenerated on
demand — rejected: contradicts the "pinned, immutable, human-approved"
contract; regeneration is version-bumped by policy, so an ignored artifact
would silently vary across checkouts. (c) Storing under `artifacts/` —
rejected: `artifacts/` holds run/eval outputs; the approved text artifact
is data input to the import, so it belongs next to the other pinned inputs.

## R10 — Seed handling on the llama.cpp endpoint

**Decision**: The generator passes a fixed integer seed (CLI `--seed`,
default a recorded constant) through to the chat-completion request (DSPy
LM kwargs) and records it in the manifest. Preflight (reusing
`app/ai/llm.py` verification) runs one seeded smoke call before the run;
if the endpoint errors on the parameter, the run stops loudly (no-fallback
discipline). The manifest records the seed value plus, for honesty, that
cross-environment byte-identical regeneration is NOT claimed (spec
Assumptions: governance = validation + pinning, not bit-reproducibility).

**Rationale**: llama.cpp's OpenAI-compatible server accepts a `seed`
sampling parameter; at temperature 0 decoding is greedy and the seed
primarily pins incidental sampler state. Recording it satisfies FR-002/FR-012
without over-claiming determinism.

**Alternatives considered**: Claiming full byte-reproducibility — rejected:
not guaranteed across llama.cpp builds/hardware and explicitly disclaimed
by the approved spec.

## R11 — Test strategy (stubbed LM for unit, live for gated validation)

**Decision**: Unit tests stub the LM with `dspy.utils.DummyLM` (scripted
JSON responses), covering: entry-schema acceptance/rejection, ticket_id set
mismatch detection, retry-then-fail behavior, checkpoint write/resume
(including simulated interruption: partial checkpoint -> resume -> complete
exactly-once coverage), and every validation-suite rule with canary inputs.
Integration tests cover import (atomicity, NULL rule, idempotency, manifest
extension) and GraphJin exposure (read of the 3 columns, is-null filter =
250, writes still rejected). The REAL generation run is not a pytest test;
it is a quickstart/validation procedure whose outputs (artifact + manifest)
are committed and then verified by the deterministic suite in tests.

**Rationale**: AGENTS.md forbids simulated results for shipped artifacts
but unit tests with stubbed LMs are standard practice for logic testing
(the artifact itself only ever comes from a real recorded run); keeping the
412-call live run out of pytest keeps the 417-test suite fast and
hermetic.

**Alternatives considered**: Live-LM pytest integration test — rejected as
default: endpoint availability would gate unrelated CI; a live sample run
is part of quickstart validation instead.
