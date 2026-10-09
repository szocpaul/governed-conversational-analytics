# Quickstart: Conversational Query Pipeline (feature 002)

Ask natural-language questions over the governed ITSM dataset and receive
evidence-backed answers with a sanitized trace and latency. All data access
goes through the GraphJin governed surface from feature 001; the model never
receives arbitrary SQL or unrestricted credentials.

## Prerequisites

- Feature 001 foundation running: PostgreSQL on `127.0.0.1:5432` and GraphJin
  on `127.0.0.1:8081` (`sudo docker compose up -d`).
- The pinned local llama.cpp endpoint reachable and serving the exact model
  (verified by preflight).

## Model preflight (required before model-dependent work)

```bash
cp .env.example .env   # set LLM_BASE_URL and LLM_MODEL to the pinned values
                       # (the exact pinned values are in artifacts/llm-preflight.json
                       #  and the runner report; .env.example only has placeholders)
python3 -m app.ai.preflight
```

The application loads `.env` automatically at startup (`load_dotenv()` in
`app/main.py`) — no manual `export` is needed.

Preflight verifies, with **no fallback**:
1. `GET /v1/models` lists the exact requested model ID;
2. one deterministic chat completion succeeds;
3. one typed DSPy prediction succeeds.

It writes non-secret metadata to `artifacts/llm-preflight.json`. If any check
fails it exits non-zero and you must STOP — do not switch models or providers.

The verified exact API model ID for this deployment is recorded in
`artifacts/llm-preflight.json` (`exact_model_id`).

## Configuration

Environment variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `openai-compatible` (only supported provider) |
| `LLM_BASE_URL` | local llama.cpp OpenAI-compatible base URL (private; never exposed in traces) |
| `LLM_MODEL` | exact model ID from `/v1/models` (pinned) |
| `LLM_API_KEY` | `local-not-required` |
| `LLM_TEMPERATURE` | `0` for measured runs |
| `LLM_CACHE` | `false` for measured runs |
| `GRAPHJIN_GRAPHQL_URL` | governed GraphQL endpoint (`http://127.0.0.1:8081/api/v1/graphql`) |

## After a host or Docker restart (known issue)

The GraphJin container can start before PostgreSQL is ready, lose its schema
snapshot, and answer every query with "GraphJin not initialized - no database
configured". Fix by restarting GraphJin once PostgreSQL is healthy:

```bash
sudo docker restart itsm-foundation-graphjin-1
```

## Run the API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then:

```bash
curl -s -X POST http://127.0.0.1:8000/query   -H 'Content-Type: application/json'   -d '{"question": "How many P1 tickets are there?"}'
```

## Supported question patterns

- **Aggregation**: "How many tickets are P1?", "What is the average
  resolution time?", "What is the maximum time to first response?"
- **Filtered lists**: "List 5 high-priority tickets.", "Show tickets in the
  Account Access category."
- **Relationships**: "Show tickets with their merchant names.", "Which agent
  is assigned to ticket 847201?"
- **Time filters**: "How many tickets were created after 2026-01-01?"

Entities and fields are strictly limited to the governed allowlist
(`tickets`, `merchants`, `agents` and their allowlisted columns). Requests
outside this surface are refused.

## Response shape

Every completed request returns:

```json
{
  "status": "answered | clarification | unsupported | dependency_error",
  "answer": "...",
  "evidence": {"rows": [], "aggregate": {"count": 112}, "row_count": 0},
  "trace": [{"event": "classified"}, {"event": "validated"}, {"event": "executed"}, {"event": "answered"}],
  "latency_ms": 123.4
}
```

## Trace fields

The sanitized `trace` lists pipeline events in order: `received`,
`classified`, `validated`, `executed`, `answered` (or `clarification` /
`refused` / `error`). Details are sanitized: private endpoint URLs, bearer
tokens, and IP:port pairs are redacted before storage.

## Failure behavior (stable categories)

- **Ambiguous question** -> `clarification`, no data query executed.
- **Unsupported / out-of-scope question** -> `unsupported`, no query executed.
- **Policy-violating planned request** -> `unsupported`.
- **Model or GraphJin dependency failure** -> `dependency_error`, **no
  fallback** to another model or provider is attempted.
- **Ungrounded answer** (a factual value not present in evidence) -> refused
  as `clarification`; the fabricated value is never returned.

## Validation gates

```bash
pytest -q tests/unit tests/contract
pytest -q tests/integration/test_conversational_flow.py
```
