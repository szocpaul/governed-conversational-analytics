# Contract: Extended ClassifyQuestion Signature

**Module**: `app/ai/signatures.py` — the existing `ClassifyQuestion` gains two
content categories. The docstring is the versioned instruction (house
discipline); `PROMPT_VERSION` is bumped.

## Output categories (the `category` field)

| Category | Meaning | Routed to |
|---|---|---|
| `content_about` | Find tickets by their text content (incl. deep paraphrases with zero shared keywords) | governed retrieval, mode=about |
| `content_similar` | Find tickets similar to a referenced ticket | governed retrieval, mode=similar |
| `supported` | A structured analytical question (list/aggregate/group_by) | structured planner (unchanged) |
| `ambiguous` | Materially ambiguous / multi-part | stable clarification (unchanged) |
| `unsupported` | Out of scope / unsupported query shape / prohibited | stable refusal (unchanged) |

## Instruction guidance (docstring contract)

- A question is `content_about` when it asks to FIND tickets by what they are
  ABOUT — their text content — even when it shares no keywords with the
  tickets (e.g. "customers unable to complete a purchase because their card
  was rejected" -> content_about).
- A question is `content_similar` when it asks for tickets SIMILAR to a
  referenced ticket (a ticket id is present or implied).
- A question asking for a COUNT, AGGREGATE, or GROUPED BREAKDOWN is
  `supported` even if it mentions a topic ("how many tickets about login" ->
  supported, not content_about).
- When uncertain, prefer `supported` (conservative fallback — research R3).

## Guarantees (verified by tests)

- The `category` output parses to exactly one of the five categories;
  unparseable/unknown output triggers the conservative fallback.
- The classifier never outputs a ticket_id; id extraction is deterministic
  (contracts/routing-integration.md).
- No new model call is added: the same classifier call routes content.
