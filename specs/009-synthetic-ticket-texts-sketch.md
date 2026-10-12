# Feature Sketch: Synthetic Ticket Texts + Hybrid Search (009)

**Status**: Sketch — NOT yet a spec. Human review requested before any
`/speckit-specify`. Created 2026-10-12 from the user's choice of "option B"
(synthetic ticket texts to enable meaningful hybrid search) in the RAG
discussion.
**Depends on**: specs 001-006, 008 complete.

## Origin

The user asked which RAG components make sense for this project. Analysis
conclusion: the dataset is purely structured (19 columns, no free text), so
hybrid search has little value without text. The user chose **option B**:
deterministically generate three text fields per ticket —
`short_description`, `description`, `resolution_notes` — then later build
hybrid search on top. This sketch covers the TEXT GENERATION feature; the
hybrid search itself is a follow-up sketch (see "Out of scope").

## Hard constraints from AGENTS.md

- "DO NOT silently generate replacement dataset records." → The generation
  MUST be an explicit, versioned, deterministic, auditable pipeline with a
  provenance manifest — never an ad-hoc or LLM-black-box step.
- "DO NOT use real organizational data or personal data." → All generated
  text stays synthetic; templates are hand-authored.
- "DO NOT replace the approved dataset if its pinned source cannot be
  verified." → The pinned `data/raw/tickets.csv` stays byte-identical and
  remains the source of truth for all existing columns. Generated text is
  ADDITIVE (new columns/new file), never a modification of pinned raw data.
- Tooling rejected after evaluation:
  - `avbiswas/text-albumentations` — LLM-based instruction-tuning dataset
    generator (Alpaca rows), non-deterministic, wrong output shape,
    black-box generation. Does not fit the determinism discipline.
  - `MaximeRivest/attachments` — document parsing layer (PDF/HTML/docx →
    LLM-ready text). Not needed for generation; noted as the parsing
    candidate if a future document corpus (former "option C") arrives.
    Caveats if ever used: service-fallback mode must be disabled (no
    external calls), pin the version (1.0 is beta), install only needed
    extras.

## Proposed pipeline

```text
data/raw/tickets.csv              (pinned, UNCHANGED)
    |
    v
scripts/generate_ticket_texts.py  (NEW, deterministic)
    - input: pinned tickets.csv
    - templates: data/templates/ticket_texts.yml (NEW, hand-authored,
      versioned; per category x sub_category)
    - fixed RNG seed (recorded); slot-filling from ticket columns
      (priority, merchant tier, SLA flags, timestamps)
    - output: data/raw/tickets_texts.csv (NEW, versioned, SHA-256)
    - provenance: data/raw/texts-manifest.json
      (generator script hash, template file hash, seed, row count,
      output SHA-256, created_at)
    |
    v
database/schema.sql               (MODIFIED: tickets + 3 text columns,
                                   or separate ticket_texts table — DECIDE)
scripts/import_dataset.py         (MODIFIED: imports tickets_texts.csv
                                   atomically together with tickets.csv)
    |
    v
artifacts/import-manifest.json    (extended with texts-manifest hash)
```

Determinism contract: same tickets.csv + same template version + same seed
→ byte-identical tickets_texts.csv. CI/test regenerates and compares
checksums.

## The three fields

| Field | Shape | Rules |
|---|---|---|
| `short_description` | one sentence, <= ~80 chars | names the problem + key slot (error code, subsystem); mirrors sub_category |
| `description` | 2-4 sentences | reporter context, scope, trigger, impact, workaround; slots filled from ticket columns (priority affects tone/urgency wording) |
| `resolution_notes` | 1-3 sentences | root cause, fix, verification; NULL (or absent) when the ticket is open (`closed_at IS NULL`) — DECIDE NULL vs "in progress" text |

Template example (Account Access / SSO Failure) lives in the earlier
discussion; the spec will define the full category x sub_category matrix
(every existing sub_category MUST have at least one template — coverage
checked by a unit test).

## Open decisions (need human input before spec)

1. **Schema shape**: (a) ALTER `itsm.tickets` + 3 columns, or (b) separate
   `itsm.ticket_texts` table joined on `ticket_id`. (a) is simpler for
   GraphJin exposure and later hybrid search; (b) keeps pinned data and
   generated data physically separate. Recommendation: (a) with a clear
   comment that these columns are generated, since GraphJin allowlists are
   explicit anyway.
2. **Open tickets**: `resolution_notes` = SQL NULL (recommended; honest
   data, exercises is-null filtering from feature 005) or a fixed
   "investigation in progress" string?
3. **Language**: English only (dataset, UI, and templates are English).
   Confirmation requested.
4. **Regeneration policy**: any template change = new template version +
   full regeneration + new checksums + import-manifest update. Never
   partial regeneration. Confirm.
5. **GraphJin exposure**: expose the 3 new columns read-only via GraphJin
   allowlists in THIS feature (needed by the later hybrid search) or defer
   exposure to the hybrid-search feature? Recommendation: expose now
   (read-only, small), so the data foundation is complete.

## Testing & quality gates (proposed)

- Unit: template coverage (every category x sub_category has templates),
  slot-fill validity (no unresolved `{slot}` in output), length limits,
  resolution NULL exactly when ticket is open, determinism (two runs →
  identical SHA-256).
- Integration: import is atomic; row count matches tickets.csv (2057);
  re-import idempotent; reset path still clean.
- Security: GraphJin still read-only; new columns contain no credential-
  like strings (canary scan over generated text); no PII patterns.
- Provenance: `data/raw/texts-manifest.json` + updated
  `artifacts/import-manifest.json` committed; checksums verified in tests.

## Out of scope (this feature)

- Hybrid search itself (BM25/tsvector + pgvector + fusion, governed
  retrieval boundary, retrieval trace, answer integration). Follow-up
  feature 010 sketch once 009 lands.
- Any document corpus / parsing (former "option C").
- UI changes. (A later demo touch could surface text search examples in the
  feature-008 gallery, but that belongs to the search feature.)

## Rough size estimate

Templates for ~20 sub_categories x 3 fields, generator script (~150 lines),
schema/import changes, ~15-20 tests. Comparable to a small feature
(between 001 and 008 in size).

## Resolved decisions (human-approved 2026-10-12)

1. **Schema shape**: (a) — `itsm.tickets` gets the 3 generated columns
   (marked as generated in schema comments); GraphJin allowlists stay
   explicit anyway.
2. **Open tickets**: `resolution_notes` = SQL NULL when `closed_at IS NULL`
   (honest data; exercises feature-005 is-null filtering).
3. **Language**: English only.
4. **Regeneration policy**: any template change = new template version +
   full regeneration + new checksums; never partial regeneration.
5. **GraphJin exposure**: expose the 3 new columns read-only in THIS
   feature, so the data foundation is complete for the later hybrid-search
   feature.
