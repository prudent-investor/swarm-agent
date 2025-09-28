# Agent Swarm Platform

A production-ready multi-agent platform that orchestrates router, knowledge, support, and human hand-off agents to answer InfinitePay customer questions. The solution couples a FastAPI backend, a modern React frontend, and a Retrieval Augmented Generation (RAG) pipeline that ingests the official product website.

## Repository Structure

```
.
├── agent-workflow/
│   ├── app/
│   │   ├── agents/            # Router, knowledge, support, custom, and Slack agent implementations
│   │   ├── core/              # FastAPI bootstrapping, dependency wiring, and shared configuration
│   │   ├── guardrails/        # Normalisation, moderation, and safety checks invoked on every request
│   │   ├── observability/     # Structured logging, metrics exporters, and health/readiness probes
│   │   └── services/          # Support ticket tooling, data access helpers, and Slack hand-off utilities
│   ├── data/
│   │   └── rag/               # Local vector store abstractions and chunk management
│   ├── scripts/               # Developer tooling (RAG ingestion, cache warm-up, maintenance jobs)
│   └── tests/                 # Pytest suites that exercise routing, guardrails, RAG, and API contracts
├── app/                       # Standalone scripts for operating the RAG pipeline outside the API surface
├── frontend/
│   ├── public/                # Static assets served by Vite
│   ├── src/
│   │   ├── components/        # Chat interface, status cards, metrics viewers
│   │   ├── pages/             # Chat, Status, and Metrics routes
│   │   └── lib/               # API client, query helpers, and shared UI utilities
│   └── tests/ (placeholder)   # Location reserved for Vitest/RTL suites
├── data/                      # Materialised RAG artefacts: crawled pages, chunks, embeddings, manifests
├── scripts/                   # Top-level convenience commands (wrapper around agent-workflow/scripts)
├── Dockerfile.backend         # Backend container image (Uvicorn + FastAPI)
├── Dockerfile.frontend        # Frontend container image (Nginx + static bundle)
├── docker-compose.yml         # Local topology that links backend/frontend containers and shared volumes
└── requirements.txt           # Root dependency lock for backend tooling
```

### How to Navigate the Codebase

* **Backend development** lives under `agent-workflow/app/`. Start with `main.py` to see the FastAPI entry point, `agents/` to inspect the orchestration logic, and `guardrails/` or `observability/` to understand request hardening and telemetry.
* **RAG operations** are concentrated in `agent-workflow/scripts/` (production tasks) and mirrored in `app/` for ad-hoc experimentation. Generated artefacts are written to `data/rag/` so they can be shared between local runs and container builds.
* **Frontend work** happens in `frontend/src/`. Components render the chat timeline, while the `pages/` directory maps to top-level routes. The frontend expects the backend on port `8000` and can be configured through `frontend/.env`.
* **Deployment assets** are located at the repository root: Dockerfiles, `docker-compose.yml`, and helper scripts. This keeps infrastructure-as-code visible for new contributors.

## Architecture Overview

### Message Topology

1. `POST /chat` receives the user payload and normalises it through the Guardrails service (prompt-injection filtering, PII masking, moderation, and quota validation).
2. The RouterAgent classifies the intent (knowledge, support, custom, or Slack hand-off). When the confidence drops below the configured threshold, it triggers a redirect response instead of contacting downstream agents.
3. The selected agent processes the request:
   * **KnowledgeAgent v2** enriches the prompt with context from the local RAG index (and optional web search) and always replies with citations.
   * **CustomerSupportAgent v2** combines FAQ retrieval, ticket creation, policy decisions, and escalation heuristics using dedicated tools.
   * **CustomAgent** provides a safe fallback for off-topic conversations.
   * **SlackAgent** confirms or executes human escalations by coordinating with the in-memory hand-off flow and Slack client stub.
4. Responses propagate telemetry (`correlation_id`, latency buckets, guardrail flags) and are exported through the Prometheus registry for `GET /metrics`.

### Agent Responsibilities

| Agent | Scope | Key Modules |
| --- | --- | --- |
| RouterAgent | Intent detection, OpenAI-backed classification with deterministic JSON output, language normalisation, and manual fallbacks. | `agent-workflow/app/agents/router_agent.py` |
| KnowledgeAgent v2 | Retrieval augmented answers grounded on InfinitePay documentation, caching, heuristics-based re-ranking, and optional web search fallback. | `agent-workflow/app/agents/knowledge_agent_v2.py` |
| CustomerSupportAgent v2 | FAQ matcher, ticket generator, policy evaluation (`decide`), and escalation gating with human confirmation. | `agent-workflow/app/agents/support_agent_v2.py`, `agent-workflow/app/services/support_service.py` |
| CustomAgent | Lightweight templated replies for small talk or unsupported topics. | `agent-workflow/app/agents/custom_agent.py` |
| SlackAgent | Human hand-off workflow with confirmation tokens, Slack payload formatting, and retry-aware metrics. | `agent-workflow/app/agents/slack_agent.py` |

### Guardrails & Safety Layer

The Guardrails service strips accents/symbols, blocks prompt-injection patterns, masks email/phone identifiers, enforces output truncation, and integrates with OpenAI moderation models. Diagnostics are exposed through `GET /guardrails/diagnostics` when enabled.

### Observability & Operations

* Structured JSON logging with correlation identifiers for every request.
* Prometheus metrics covering per-agent request counters, latency histograms, redirect totals, and guardrail violations (`agent-workflow/app/observability/metrics.py`).
* Readiness and health endpoints that monitor CPU/memory thresholds and bootstrapping state.
* Redirect engine that issues human hand-off tickets when guardrails escalate or router confidence is too low.

## Product Strategy & Architectural Decisions

The platform is designed to answer InfinitePay customer questions with predictable behaviour and auditable guardrails. Each decision below clarifies **how** the component operates and **why** it exists.

### Intent-guided Multi-agent Orchestration

* **Strategy** – A central `RouterAgent` classifies every message and delegates to specialised agents (Knowledge, Support, Custom, Slack) instead of relying on a single general-purpose model.
* **Motivation** – Splitting responsibilities reduces hallucinations, allows domain-specific tooling (RAG, support policies), and exposes agent-level metrics for tuning.
* **Foundations** – Single-responsibility design, composite AI pipelines, and enterprise assistant guidance balancing accuracy against cost.

### Retrieval-grounded Responses

* **Strategy** – `KnowledgeAgent v2` combines local index retrieval, heuristic re-ranking, and optional web search to deliver cited answers as the knowledge base evolves.
* **Motivation** – Pure LLM responses risk misinformation; RAG keeps answers anchored to official pages and supports auditability (links and metadata).
* **Foundations** – Retrieval-Augmented Generation best practices, `text-embedding-3-small` vectors, overlapping chunking, and versioned manifests in `data/rag/index/`.

### Guardrails Before and After the LLM

* **Strategy** – A safety pipeline normalises text, detects prompt injection, masks PII, and applies automated moderation on every `POST /chat` request.
* **Motivation** – Prevents malicious input from manipulating the session, protects sensitive data, and ensures compliance with internal and legal policies.
* **Foundations** – OWASP Conversational AI guidance, OpenAI usage recommendations, and financial-services experience with regulated support flows.

### Deliberate Human Hand-off

* **Strategy** – `SlackAgent` confirms user intent, creates tickets, and tracks state in memory. The router redirects when confidence is low or guardrails block the request.
* **Motivation** – Acknowledging model limits ensures customer issues reach human agents instead of stalling with partial answers.
* **Foundations** – Contact-centre patterns (FCR and escalation), satisfaction metrics (CSAT), and fail-safe policies.

### End-to-end Observability

* **Strategy** – Structured logging, Prometheus metrics, propagated `correlation_id`, and dedicated health endpoints.
* **Motivation** – Accelerates incident diagnosis, quantifies per-agent latency, and validates ingestion plus guardrail health.
* **Foundations** – SRE practices, Prometheus telemetry, and readiness probes for resilient deployments.

### Reproducible Operations

* **Strategy** – Separate Dockerfiles (frontend/backend), Docker Compose for local environments, ingestion scripts with offline modes, and automated tests (`pytest`, `npm run build`).
* **Motivation** – Streamlines onboarding, ensures deterministic builds, and provides clear pathways for CI/CD automation.
* **Foundations** – Infrastructure-as-code, Twelve-Factor principles, and continuous integration with isolated environments.

### Knowledge Evolution

* **Strategy** – Versioned RAG pipeline with manifests, caches, and ranking heuristics (`title_boost`, `exact_term_boost`, `length_penalty`).
* **Motivation** – Adapts to product changes without re-engineering the backend while preserving history for audits.
* **Foundations** – Incremental ingestion workflows, deterministic hashing, and metadata-rich manifests stored under `data/rag/index/`.

## RAG Ingestion Pipeline

The ingestion pipeline crawls InfinitePay public pages (see `data/rag/sources/seed_urls.txt`) and produces artefacts consumed by the KnowledgeAgent:

1. **Load** – Crawl whitelisted URLs with configurable depth, timeout, and request pacing.
2. **Clean** – Strip navigation chrome, deduplicate paragraphs, and hash content for idempotency.
3. **Split** – Chunk documents with overlap; compute metadata including titles, order, and canonical URLs.
4. **Embed** – Generate embeddings via OpenAI (`text-embedding-3-small`) and persist them alongside cleaned text.
5. **Index** – Produce manifest JSONL files, caches, and hashed chunk registries under `data/rag/index/`.

`python scripts/run_rag_dry_run.py` executes offline until the split step, while `python scripts/run_rag_pipeline.py` runs the full pipeline (requires network access and valid OpenAI credentials). The KnowledgeAgent leverages heuristic reranking (`title_boost`, `exact_term_boost`, `length_penalty`), query caching with TTL, fallback messaging, and optional web search to satisfy low-recall scenarios.

## Frontend Experience

The React single-page application offers three core surfaces:

* **Chat Console** – Conversation view with agent-specific styling, clickable citations, correlation IDs, clipboard shortcuts, and localStorage persistence (`frontend/src/components/Chat.tsx`).
* **Status Page** – Visualises `/health` and `/readiness` payloads, including JSON payload dumps and status indicators (`frontend/src/pages/Status.tsx`).
* **Metrics Page** – Streams the raw Prometheus exposition with manual refresh and export-ready formatting (`frontend/src/pages/Metrics.tsx`).

TailwindCSS powers the visual system, while Vite handles development and production builds.

## Deployment Topologies

| Scenario | Description |
| --- | --- |
| Local development | Run FastAPI with Uvicorn and the React dev server independently. Ideal for rapid iteration and unit testing. |
| Docker Compose | `docker compose up --build` launches backend and frontend containers on a shared `agentnet` bridge network, persisting RAG artefacts to `./data`. |
| Standalone images | `Dockerfile.backend` exposes `uvicorn app.main:app --host 0.0.0.0 --port 8000`, while `Dockerfile.frontend` bundles the static site behind Nginx on port `80`. Suitable for Render, Vercel, or other managed platforms. |

## Build & Run Instructions

### Backend (FastAPI)

```bash
cd agent-workflow
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

`/docs`, `/health`, `/readiness`, `/route`, `/chat`, and `/metrics` become available once the server boots.

### Frontend (React)

```bash
cd frontend
npm install
cp .env.example .env  # optional; defaults to http://127.0.0.1:8000
npm run dev  # opens http://localhost:5173
```

To produce a distributable bundle, execute `npm run build` and optionally `npm run preview` to verify the generated `dist/` output.

### Docker

```bash
docker compose up --build
```

This command builds both images, starts the backend on `http://localhost:8000`, and serves the frontend via Nginx on `http://localhost`. To stop the stack run `docker compose down` (add `-v` to prune volumes). Individual images can be built with:

```bash
docker build -f Dockerfile.backend -t agent-backend .
docker build -f Dockerfile.frontend -t agent-frontend .
```

## Testing Strategy

* **FastAPI + Agents** – `pytest` suite covering health checks, routing logic, guardrails, metrics, persistence, and the RAG admin endpoints (`agent-workflow/tests/`). OpenAI calls are stubbed to keep tests deterministic and offline.
* **RAG Pipeline** – Unit tests validate chunking, manifest creation, and persistence across the ingestion pipeline.
* **Frontend** – Manual verification via Vite dev server; the build step is exercised through CI by `npm run build`.

Execute backend tests with:

```bash
cd agent-workflow
pytest
```

## Challenge Coverage

| Requirement (case proposal) | Implementation |
| --- | --- |
| Three distinct agents orchestrated by a router | RouterAgent dispatches to KnowledgeAgent, CustomerSupportAgent, CustomAgent, and SlackAgent with correlation-aware telemetry. |
| Knowledge agent grounded on InfinitePay content | RAG pipeline ingests the listed URLs and the KnowledgeAgent answers with mandatory citations and web-search fallback. |
| Customer support agent with tooling | SupportService wraps FAQ search, ticket management, policy decisions, and escalation prompts, exposing extra metadata for hand-offs. |
| HTTP API entry point | `POST /chat` accepts `{ "message": str, "user_id": Optional[str] }` and returns JSON with agent, content, citations, and metadata. |
| Dockerisation | Dedicated Dockerfiles and Compose topology orchestrate backend + frontend containers with shared network and persisted data. |
| Testing strategy | Comprehensive pytest suite exercises routing, guardrails, metrics, and RAG components, described in this README and in `agent-workflow/README.md`. |
| Bonus challenges | SlackAgent handles human hand-off confirmation, Guardrails enforce safe prompting and PII masking, and redirect logic escalates low-confidence routes. |

## Further Enhancements

* Plug an actual Slack API client and ticketing integration in place of the in-memory stubs.
* Expand the frontend with automated tests (Vitest/Testing Library) and screenshot baselines.
* Introduce horizontal scaling guidelines (Redis cache for RAG queries, distributed tracing via OpenTelemetry exporters).
* Extend the RAG whitelist with marketing campaigns while preserving guardrail filters and per-source versioning.

For backend internals and environment variable reference see [`agent-workflow/README.md`](agent-workflow/README.md).
