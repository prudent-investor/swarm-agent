# Agent Workflow Backend

The `agent-workflow/` package contains the FastAPI backend that orchestrates the agent swarm, exposes observability surfaces, and delivers the Retrieval Augmented Generation (RAG) toolchain.

## Directory Layout

```
app/
├── agents/                # Router, knowledge, support, custom, and Slack hand-off agents
├── guardrails/            # Prompt-injection, moderation, PII masking and validation helpers
├── observability/         # Prometheus metrics, tracing, and logging utilities
├── rag/                   # End-to-end pipeline for loading, cleaning, chunking, embedding, and indexing content
├── routers/               # FastAPI routers for health, chat, router-only validation, and RAG admin
├── schemas/               # Pydantic models used by the HTTP interface
├── services/              # Shared integrations (LLM provider, cache helpers, Slack hand-off stub)
├── settings.py            # Centralised configuration powered by pydantic-settings
└── utils/                 # Runtime helpers

scripts/
├── run_rag_dry_run.py     # Offline dry-run without network or embeddings
└── run_rag_pipeline.py    # Full ingestion + embedding pipeline

data/rag/                  # Raw pages, cleaned chunks, embeddings, and manifest outputs

tests/                     # API, agent, guardrails, RAG, and persistence tests
```

## Environment Setup

1. Create a virtual environment: `python -m venv .venv`
2. Activate it:
   * PowerShell: `.\.venv\Scripts\Activate.ps1`
   * CMD: `.\.venv\Scripts\activate.bat`
   * macOS/Linux: `source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy the sample environment: `cp .env.example .env`
5. Provide the OpenAI credentials and adjust limits to suit your environment.

## Running the API Locally

```bash
uvicorn app.main:app --reload
```

* OpenAPI docs: http://127.0.0.1:8000/docs
* Health endpoint: http://127.0.0.1:8000/health
* Readiness endpoint: http://127.0.0.1:8000/readiness (when enabled)

## Automated Tests

Execute the suite from this directory:

```bash
pytest
```

Tests stub the OpenAI client and external network access, so they run fully offline.

After starting the API (or pointing `BASE_URL` to a deployed host) you can execute the end-to-end smoke suite from the repository root:

```bash
./smoke-tests.sh
```

## Key Environment Variables

| Variable | Purpose |
| --- | --- |
| `APP_NAME`, `APP_VERSION`, `APP_PORT` | Metadata reported by the API |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` | Models used by router, router heuristics, and RAG embeddings |
| `RAG_*` | Crawl, chunk, cache, and scoring configuration for the pipeline |
| `WEB_SEARCH_*` | Enable, select provider, and authenticate outbound search |
| `SUPPORT_*` | Tune FAQ thresholds, ticket persistence, escalation, and masking behaviour |
| `GUARDRAILS_*`, `PII_*` | Prompt-injection detection, moderation, normalisation, and PII masking flags |
| `SLACK_*`, `SLACK_AGENT_ENABLED`, `HANDOFF_CONFIRM_TTL_SECONDS` | Slack client credentials, modes (mock/real), and user confirmation TTL |
| `REDIRECT_*` | Manual/low-confidence redirect thresholds before calling agents |
| `METRICS_ENABLED`, `LOG_FORMAT`, `CORRELATION_ID_HEADER` | Prometheus exposure and structured logging controls |
| `READINESS_*` | CPU and memory guard thresholds for readiness checks |
| `FRONTEND_ALLOWED_ORIGINS` | Permitted origins for the frontend application |

Refer to `settings.py` for the complete catalogue and defaults.

## RAG Pipeline Overview

The ingestion pipeline harvests InfinitePay public pages, normalises them, and emits versioned JSONL artefacts:

1. **Load** – Fetch every whitelisted URL under `data/rag/sources/` with backoff, timeout, and depth constraints.
2. **Clean** – Strip navigation chrome, deduplicate, and keep only relevant textual paragraphs.
3. **Split** – Chunk content with configurable overlap while preserving page metadata.
4. **Embed** – Generate embeddings with OpenAI (skipped in dry-run mode) and persist vector metadata.
5. **Index** – Assemble retriever-ready manifests consumed by the `KnowledgeAgent`.

`run_rag_dry_run.py` executes up to the split step without touching the network, making it ideal for CI. `run_rag_pipeline.py` performs the full run and writes manifests to `data/rag/index/`.

## Agent Responsibilities

* **RouterAgent** – Scores the incoming message, annotates routing metadata, and selects the downstream agent.
* **KnowledgeAgent** – Answers InfinitePay product questions using the local RAG index and provides mandatory citations.
* **SupportAgent** – Collects account troubleshooting details and orchestrates support tool usage.
* **CustomAgent** – Handles general chit-chat or out-of-scope questions with graceful fallbacks.
* **SlackAgent (bonus)** – Emits human hand-off tickets when guardrails or router confidence require escalation.

Guardrails wrap every request to remove prompt-injection attempts, mask PII, and block disallowed content before the agents are invoked.

## Administrative Endpoints

* `POST /route` – Unit-testable router classification without engaging downstream agents.
* `POST /chat` – Full end-to-end message handling with correlation identifiers and guardrail telemetry.
* `POST /rag/reindex` – Protected endpoint that replays the RAG pipeline when enabled via configuration.
* `GET /metrics` – Prometheus exposition with per-agent counters, histograms, and correlation labels.
* `GET /guardrails/diagnostics` – Optional debugging surface that reveals masked inputs and detected violations.

For the global documentation, deployment topology, and frontend overview see the repository root `README.md`.
