# Governed Conversational Analytics

A demonstration of natural-language analytics over a synthetic IT support dataset. Ask questions in plain English, and the application retrieves relevant data using controlled, read-only query paths.

The project explores how LLM-assisted query planning can be combined with deterministic validation, restricted database access, and evaluation.

> This is a local demo, not a production-ready multi-user service. Its security controls and evaluation results do not guarantee that every answer is correct or prevent every possible disclosure.

## What it does

The demo answers questions about tickets, merchants, and agents in PostgreSQL. It routes questions to different paths:

- **Structured analytics:** an LLM produces a typed query request. The application validates the request and executes it through GraphJin.
- **Ticket-text search:** the application combines keyword and semantic search using fixed, parameterized PostgreSQL queries. It merges the ranked results and uses selected ticket summaries as evidence.
- **Content counts:** the application counts tickets matching a defined combination of keyword search and a calibrated semantic-similarity threshold.

The application uses a read-only database role for these paths. The model does not generate or execute arbitrary SQL.

### Example questions

- “How many P1 tickets are there?”
- “Which category has the most tickets?”
- “Show me tickets about login problems.”
- “Find tickets similar to ticket 847203.”
- “How many tickets are about login?”

The demo UI includes a gallery of example questions and returns evidence, an execution trace, and latency with its responses. Ambiguous, unsupported, and dependency-failure cases are reported separately.

## Architecture

```text
                     Plain-English question
                               |
                               v
                   DSPy question classification
                               |
                +--------------+----------------+
                |                               |
                v                               v
      Structured analytics              Text search / count
                |                               |
      Typed request + validation        Embedding + fixed queries
                |                               |
             GraphJin                  Parameterized SQL
                |                               |
                +--------------+----------------+
                               |
                               v
                    Read-only PostgreSQL
                               |
                               v
                     Evidence + LLM answer
```

The structured path uses GraphJin's read-only policy. The text-search and content-count paths connect directly to PostgreSQL rather than going through GraphJin. They use a separate read-only channel with fixed parameterized statements; GraphJin's field policy does not govern that channel.

Hybrid search combines PostgreSQL full-text ranking with pgvector cosine similarity, then merges the rankings using reciprocal rank fusion. Content counts use an uncapped SQL count over a **lexical OR semantic-threshold** match. The count is exact for that match rule, not necessarily for every ticket a person would consider relevant to the topic.

The application uses a chat-model endpoint for classification, structured query planning, and answer generation. A separate embedding endpoint supplies vectors for content questions. Offline scripts prepare and validate generated ticket texts and embeddings; an evaluation toolkit runs cases against the application and compares results with a baseline.

## Security approach

The LLM is not the authorization layer. The demo uses several controls:

- Typed request schemas and allowlists for supported structured queries.
- Deterministic validation before structured query execution.
- A default-block GraphJin policy for structured access.
- A read-only PostgreSQL role for application queries.
- Fixed, parameterized SQL, field restrictions, and result limits for text retrieval.
- Prompt-injection classification for telemetry, plus output and trace redaction for selected patterns.

These controls reduce risks but are not a proof of universal security or factual correctness. The content-retrieval channel has its own controls and is not mediated by GraphJin. Review authentication, network exposure, credentials, data access, and the threat model before using this design beyond a local demo.

## Evaluation

The repository's recorded held-out evaluation contains **57 cases**, including **16 security cases**. The checked-in results report:

| Metric | Recorded result |
| --- | --- |
| Structural validity | 1.0 on 42 applicable cases |
| Execution accuracy | 1.0 on 33 applicable cases |
| Prohibited effects detected | 0 |
| Disclosures detected | 0 |
| False refusals flagged | 1 |

The flagged refusal was a request to write a poem, which the system correctly identified as outside its scope. These results apply to the tested cases and do not guarantee correctness or security in every situation.

See [`artifacts/current.json`](artifacts/current.json) and [`evaluation/`](evaluation/) for details.

## Requirements

- Python 3.12 or later.
- Docker with the Compose plugin.
- A reachable OpenAI-compatible chat-model endpoint, such as a local llama.cpp server, exposing the configured model ID.
- A separate compatible embedding endpoint serving the configured model and producing 768-dimensional vectors for ticket-text search.
- Enough local resources to run or access the configured models.

The supplied configuration uses synthetic data and local development credentials. It is not suitable for exposure to untrusted networks without further hardening.

## Quick start

From a Linux or macOS shell, clone the repository and install the dependencies:

```bash
git clone https://github.com/szocpaul/governed-conversational-analytics.git
cd governed-conversational-analytics

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` before continuing:

1. Set `LLM_BASE_URL` and `LLM_MODEL` to the chat endpoint and the exact model ID it exposes.
2. Set `EMBED_BASE_URL` and `EMBED_MODEL` for the separate embedding endpoint. The application expects the configured embedding model and dimensions used by the dataset.
3. Keep the example database settings consistent with the supplied GraphJin and database role configuration for an initial local run.

After editing `.env`, export its values for the database scripts and preflight. Quote any shell-special characters in the values before running:

```bash
set -a
. ./.env
set +a
```

Start PostgreSQL, initialize the schema, and import the dataset:

```bash
docker compose up -d --wait postgres
python scripts/initialize_database.py
python scripts/import_dataset.py
```

Start GraphJin, check the configured chat model, and run the application:

```bash
docker compose up -d graphjin
python -m app.ai.preflight
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001/` in a browser. Docker may require `sudo` depending on the local installation. The import and preflight scripts write artifact files.

**Configuration note:** the supplied GraphJin development configuration and database role setup contain their own database names and credentials. Changing database values in `.env` alone can break the setup. Adapt all relevant configuration together for another environment, and do not expose the development defaults to untrusted networks.

## Tests and evaluation

Run the test suite:

```bash
python -m pytest -q
```

Some integration and security tests require the database, GraphJin, or model endpoints. Tests dependent on unavailable services may be skipped.

Run an evaluation and compare it with the recorded baseline:

```bash
python -m evaluation.run --cache=false --output artifacts/my-run.json
python -m evaluation.compare \
  --baseline artifacts/baseline.json \
  --current artifacts/my-run.json
```

The evaluation drives the application in-process and requires the configured services. It writes the specified output file. The comparison requires compatible model and evaluation-set versions; a different model may require a new baseline.

## Data

The project uses the MIT-licensed [Synthetic ITSM Helpdesk Ticket Dataset](https://github.com/drapertoby/itsm-ticket-dataset) by drapertoby, pinned to an upstream commit. It also uses generated ticket texts and embeddings for content-search demonstrations.

See [`data/raw/LICENSE`](data/raw/LICENSE) for the dataset license. That license applies to the dataset and does not by itself establish a license for the project code.

## Repository structure

| Path | Purpose |
| --- | --- |
| `app/` | API, query pipeline, retrieval, security, and demo UI |
| `database/` | PostgreSQL schema, roles, and bootstrap |
| `graphjin/config/` | GraphJin development policy |
| `scripts/` | Database initialization, import, and data preparation |
| `evaluation/` | Evaluation cases, metrics, and regression comparison |
| `tests/` | Unit, integration, security, and evaluation tests |
| `artifacts/` | Recorded results and data provenance |
| `specs/` | Feature specifications and implementation records |
| `.groma/` | Architecture map |

## Architecture documentation

The `.groma/` directory contains a Groma architecture map describing the system, actors, external dependencies, components, and flows. It includes the structured-query, content-search, content-count, data-preparation, and quality-gate flows.

If the Groma CLI is installed, the map can be inspected with:

```bash
groma view --plain
groma view web-application
groma view structured-query
```

The architecture map is documentation; consult the implementation and configuration for current runtime behavior.
