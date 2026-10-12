# Implementation Plan: Synthetic Ticket Texts

**Branch**: `[009-synthetic-ticket-texts]` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-synthetic-ticket-texts/spec.md`

## Summary

Add three synthetic free-text fields (short_description, description,
resolution_notes) to all 2057 pinned ITSM tickets so a later hybrid-search
feature has text to work with. Generation is an explicit offline pipeline:
the local pinned llama.cpp Qwen endpoint (exact pinned model ID,
temperature 0, recorded seed, no fallback) produces strictly validated JSON
through a typed DSPy 3.4.0 program, in batches of 5 tickets per call, with
JSONL checkpoint/resume and fail-loud retries. A deterministic, model-free
validation suite is the quality gate; a human per-category data-quality
review (MANUAL GATE) approves the pinned, SHA-256-checksummed artifact
before it is imported atomically into `itsm.tickets` as three additive
columns and exposed read-only through the GraphJin allowlists.

Primary requirement sources: spec.md FR-001..FR-017, SC-001..SC-007, and the
six binding human decisions recorded in the spec's Background section.

## Technical Context

**Language/Version**: Python 3.14.4 (project interpreter)

**Primary Dependencies**: dspy==3.4.0 (lm15 engine), pydantic==2.12.5,
httpx==0.28.1, psycopg==3.3.6 (feature-001 import tooling), pytest==9.0.3 —
all already pinned in the project; no new runtime services and no new
third-party dependencies are introduced by this feature.

**Storage**: PostgreSQL 16.10-alpine (pinned image, compose.yml);
GraphJin 3.21.6 (pinned image) as the governed read-only boundary;
generated artifacts as versioned JSONL + JSON manifest files in the
repository (`data/raw/tickets_texts.jsonl`, `data/raw/texts-manifest.json`).

**Testing**: pytest (417 pre-existing tests must stay green); new unit
tests (generator program with a stubbed LM, validation suite, checkpoint
resume, manifest schemas) and integration tests (import, governed read,
write rejection) in the existing tests/unit + tests/integration layout.

**Target Platform**: Linux host with Docker Compose stack (PostgreSQL +
GraphJin) and network access to the local llama.cpp endpoint via Tailscale.

**Project Type**: Data-pipeline feature for an existing web-service project
(offline build-time generator + database/import + governed read exposure).

**Performance Goals**: None as a gate (AGENTS.md: latency is observational
only). Generation is a one-time offline run of ~412 model calls
(2057 tickets / 5 per call); runtime is recorded in the manifest for
information only.

**Constraints**: Local pinned Qwen endpoint only (exact model ID, no
fallback, temperature 0, cache disabled); pinned `data/raw/tickets.csv`
byte-identical; generation is offline and never part of the runtime query
path; generated artifact pinned/immutable once human-approved; import
atomic + idempotent; GraphJin exposure read-only; no credentials, endpoint
details, or prompts in user-facing output.

**Scale/Scope**: 2057 tickets, 20 category x sub_category pairs, 3 text
fields per ticket; ~412 batched model calls; ~15-20 new tests; one new CLI
script, one new validation CLI, one new DSPy module, modifications to
schema/import/GraphJin policy.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution (`.specify/memory/constitution.md`) is an
unfilled template, so per AGENTS.md source-of-truth precedence the approved
spec plus AGENTS.md govern. Mapping of the relevant AGENTS.md prohibitions
to this design:

| AGENTS.md rule | How this plan complies |
|---|---|
| "DO NOT silently generate replacement dataset records" | Generation is an explicit CLI run with a provenance manifest, deterministic validation suite, pinned checksummed artifact, and a human MANUAL GATE before import. Nothing is silent or ad-hoc. |
| "DO NOT use real organizational data or personal data" | All text is synthetic, generated from the synthetic ITSM dataset's structured columns; the validation suite scans for credential-like/PII patterns. |
| "DO NOT replace the approved dataset if its pinned source cannot be verified" / raw data immutable | `data/raw/tickets.csv` stays byte-identical; import still verifies its pinned SHA-256 first; generated text is additive columns only. |
| "DO NOT switch to another model, hosted provider, or cloud fallback" | Generator verifies the exact pinned API model ID via `GET /v1/models` before the run (reusing `app/ai/llm.py` discipline); any mismatch is a loud stop. |
| "DO NOT simulate model, database, security, baseline, or evaluation results" | The artifact is produced by real recorded model calls; unit tests stub the LM but the shipped artifact and its manifest come only from a real run. |
| "The model MUST NOT receive an arbitrary SQL execution tool" / read-only runtime | The generator writes only files, never the database; only `scripts/import_dataset.py` (owner role, offline) writes; GraphJin stays read-only with explicit allowlists. |
| "DO NOT commit API keys, passwords, tokens, or generated secrets" | Manifests record hashes and non-secret metadata only; `.env` discipline unchanged. |
| "DO NOT tick, approve, bypass, or reinterpret any MANUAL GATE" | The human data-quality review is recorded by the human in `texts-manifest.json`; the import refuses to proceed without that human-recorded approval marker. |
| Prompt-injection / endpoint non-exposure rules | The private endpoint is used only offline by the maintainer; no endpoint details, prompts, or credentials enter UI, errors, or traces. |

No constitution/governance violations; Complexity Tracking is empty.

*Post-design re-check (after Phase 1)*: the design artifacts (research.md,
data-model.md, contracts/, quickstart.md) introduce no new conflicts with
the mapping above. Specifically: the generator never touches the database
(R7 keeps writes in the owner-role import script only); the checkpoint and
sample outputs cannot leak into the runtime path (offline CLI, separate
files); the human MANUAL GATE is machine-enforced by the import
precondition without giving agents any way to set the approval marker
(contracts/artifact-schemas.md); and no new dependencies, services, or
secrets were introduced. Gate still passes.

## Project Structure

### Documentation (this feature)

```text
specs/009-synthetic-ticket-texts/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── generator-cli.md
│   ├── validation-suite.md
│   ├── artifact-schemas.md
│   └── graphjin-policy.md
├── checklists/
│   └── requirements.md  # From /speckit-specify (already validated)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/ai/
└── text_generation.py        # NEW: typed DSPy signature + program for batch
                              #      text generation (pydantic-validated output);
                              #      holds PROMPT_VERSION constant. Offline use
                              #      only; not imported by the runtime query path.

scripts/
├── generate_ticket_texts.py  # NEW: generation CLI — preflight model
│                             #      verification, batching (5/call), JSONL
│                             #      checkpoint + resume, bounded retries,
│                             #      artifact + texts-manifest.json writing.
├── validate_ticket_texts.py  # NEW: deterministic validation-suite CLI
│                             #      (offline, no model): schema, coverage,
│                             #      length, language, secrets/PII scan,
│                             #      category consistency, NULL rule.
└── import_dataset.py         # MODIFIED: also load tickets_texts.jsonl, verify
                              #      its checksum + human-approval marker, upsert
                              #      the 3 columns in the same single transaction,
                              #      extend artifacts/import-manifest.json.

data/raw/
├── tickets.csv               # UNCHANGED, pinned, byte-identical.
├── tickets_texts.jsonl       # NEW, COMMITTED after human approval: pinned
│                             #      generated artifact (1 JSON object per line).
└── texts-manifest.json       # NEW, COMMITTED: provenance manifest (model ID,
                              #      versions, seed, prompt version, hashes,
                              #      human-review record).

database/
└── schema.sql                # MODIFIED: itsm.tickets gains short_description,
                              #      description, resolution_notes (text, nullable,
                              #      marked generated) in CREATE TABLE plus
                              #      idempotent ALTER ... IF NOT EXISTS lines.

graphjin/config/
└── policies.yml              # MODIFIED: tickets allowlist gains the 3 new
                              #      columns (read-only; nothing else changes).

artifacts/
├── import-manifest.json      # MODIFIED (additive): new top-level
│                             #      "generated_texts" key; existing keys untouched.
└── tickets_texts.checkpoint.jsonl  # NEW, transient (deleted on success):
                                    #      append-only resume checkpoint.

tests/
├── unit/
│   ├── test_text_generation_program.py   # NEW (stubbed LM, schema validation)
│   ├── test_ticket_texts_validation.py   # NEW (deterministic suite rules)
│   └── test_ticket_texts_checkpoint.py   # NEW (resume semantics)
└── integration/
    ├── test_ticket_texts_import.py       # NEW (atomic import, NULL rule,
    │                                     #      idempotency, manifest extension)
    └── test_graphjin_ticket_texts.py     # NEW (read-only exposure, is-null,
                                          #      write rejection unchanged)
```

**Structure Decision**: The feature extends the existing single-project
layout. Generation logic lives in a testable DSPy module under `app/ai/`
(mirroring `signatures.py` discipline) with thin CLIs under `scripts/`
(mirroring feature-001 tooling). The generated artifact is committed under
`data/raw/` next to the pinned raw data because it is itself pinned,
versioned, and human-approved (see research.md R7). No new services, no
frontend changes, no evaluation-corpus changes.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — nothing to justify.
