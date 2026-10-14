# Contract: Routing (content_count category)

**Files**: `app/ai/signatures.py` (classifier), `app/ai/routing.py` (dispatch),
`app/api/routes.py` (integration).

## New category

The feature 011 `ClassifyQuestion` gains `content_count`. The docstring
(versioned instruction) is extended; PROMPT_VERSION is bumped.

| Category | Meaning | Routed to |
|---|---|---|
| `content_count` | A COUNT over a TOPIC ("how many tickets about X", "how many tickets are about X") | the governed hybrid count path |

## Instruction guidance (docstring contract)

- A question asking for a COUNT over a TOPIC is `content_count`, NOT
  `supported` — the topic lives in the text, not a structured column.
- A question asking for a COUNT over a STRUCTURED value ("how many P1
  tickets", "how many tickets in category X") stays `supported`.
- A question asking for a LIST of tickets about a topic is `content_about`
  (feature 011), not `content_count`.
- When uncertain, prefer `supported` (conservative fallback).

## Dispatch (app/ai/routing.py + app/api/routes.py)

```text
content_count -> embed query text (pinned EmbeddingGemma-2)
              -> governed hybrid count (contracts/count-query.md)
              -> ground the answer on the count + up to 5 example ids
```

## Guarantees (verified by tests)

- "how many tickets about login" routes to the count path (not structured).
- "how many P1 tickets" routes to the structured path (unchanged).
- Unparseable/unknown classifier output -> conservative fallback to the
  structured path.
- The classifier is re-tuned with the approved bounded BootstrapFewShot on
  the extended dev set (routing + count cases), dev-only.
