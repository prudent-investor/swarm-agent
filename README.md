# Agent Swarm Platform

A production-ready multi-agent platform that orchestrates router, knowledge, support, and human hand-off agents to answer InfinitePay customer questions. The solution couples a FastAPI backend, a modern React frontend, and a Retrieval Augmented Generation (RAG) pipeline that ingests the official product website. The stack depends on OpenAI models for routing, retrieval augmentation, and language generation.

## Author
- Jefferson Rodrigo Schuertz (senior data engineer and project maintainer)

## Unit Test Coverage
- Command: python -m pytest --cov=app --cov-report=term
- Result: **86% line coverage (28 Sep 2025 01:40 UTC)**

## Repository Structure

`
.
??? agent-workflow/
?   ??? app/
?   ?   ??? agents/            # Router, knowledge, support, custom, and Slack agent implementations
?   ?   ??? core/              # FastAPI bootstrapping, dependency wiring, and shared configuration
?   ?   ??? guardrails/        # Normalisation, moderation, and safety checks invoked on every request
?   ?   ??? observability/     # Structured logging, metrics exporters, and health/readiness probes
?   ?   ??? services/          # Support ticket tooling, data access helpers, and Slack hand-off utilities
?   ??? data/
?   ?   ??? rag/               # Local vector store abstractions and chunk management
?   ??? scripts/               # Developer tooling (RAG ingestion, cache warm-up, maintenance jobs)
?   ??? tests/                 # Pytest suites that exercise routing, guardrails, RAG, and API contracts
??? app/                       # Standalone scripts for operating the RAG pipeline outside the API surface
??? frontend/
?   ??? public/                # Static assets served by Vite
?   ??? src/
?   ?   ??? components/        # Chat interface, status cards, metrics viewers
?   ?   ??? pages/             # Chat, Status, and Metrics routes
?   ?   ??? lib/               # API client, query helpers, and shared UI utilities
?   ??? tests/ (placeholder)   # Location reserved for Vitest/RTL suites
??? data/                      # Materialised RAG artefacts: crawled pages, chunks, embeddings, manifests
??? scripts/                   # Top-level convenience commands (wrapper around agent-workflow/scripts)
??? Dockerfile.backend         # Backend container image (Uvicorn + FastAPI)
??? Dockerfile.frontend        # Frontend container image (Nginx + static bundle)
??? docker-compose.yml         # Local topology that links backend/frontend containers and shared volumes
??? requirements.txt           # Root dependency lock for backend tooling
`

### How to Navigate the Codebase

* **Backend development** lives under gent-workflow/app/. Start with main.py to see the FastAPI entry point, gents/ to inspect the orchestration logic, and guardrails/ or observability/ to understand request hardening and telemetry.
* **RAG operations** are concentrated in gent-workflow/scripts/ (production tasks) and mirrored in pp/ for ad-hoc experimentation. Generated artefacts are written to data/rag/ so they can be shared between local runs and container builds.
* **Frontend work** happens in rontend/src/. Components render the chat timeline, while the pages/ directory maps to top-level routes. The frontend expects the backend on port 8000 and can be configured through rontend/.env.
* **Deployment assets** are located at the repository root: Dockerfiles, docker-compose.yml, and helper scripts. This keeps infrastructure-as-code visible for new contributors.

## Architecture Overview

### Message Topology

1. POST /chat receives the user payload and normalises it through the Guardrails service (prompt-injection filtering, PII masking, moderation, and quota validation).
2. The RouterAgent classifies the intent (knowledge, support, custom, or Slack hand-off). When the confidence drops below the configured threshold, it triggers a redirect response instead of contacting downstream agents.
3. The selected agent processes the request:
   * **KnowledgeAgent v2** enriches the prompt with context from the local RAG index (and optional web search) and always replies with citations.
   * **CustomerSupportAgent v2** combines FAQ retrieval, ticket creation, policy decisions, and escalation heuristics using dedicated tools.
   * **CustomAgent** provides a safe fallback for off-topic conversations.
   * **SlackAgent** confirms or executes human escalations by coordinating with the in-memory hand-off flow and Slack client stub.
4. Responses propagate telemetry (correlation_id, latency buckets, guardrail flags) and are exported through the Prometheus registry for GET /metrics.

### Agent Responsibilities

| Agent | Scope | Key Modules |
| --- | --- | --- |
| RouterAgent | Intent detection, OpenAI-backed classification with deterministic JSON output, language normalisation, and manual fallbacks. | gent-workflow/app/agents/router_agent.py |
| KnowledgeAgent v2 | Retrieval augmented answers grounded on InfinitePay documentation, caching, heuristics-based re-ranking, and optional web search fallback. | gent-workflow/app/agents/knowledge_agent_v2.py |
| CustomerSupportAgent v2 | FAQ matcher, ticket generator, policy evaluation (decide), user profile retention, account-status explanations, and escalation gating with human confirmation. | gent-workflow/app/agents/support_agent_v2.py, gent-workflow/app/services/support_service.py |
| CustomAgent | Lightweight templated replies for small talk or unsupported topics. | gent-workflow/app/agents/custom_agent.py |
| SlackAgent | Human hand-off workflow with confirmation tokens, Slack payload formatting, and retry-aware metrics. | gent-workflow/app/agents/slack_agent.py |

### Guardrails and Safety Layer

The Guardrails service strips accents and symbols, blocks prompt-injection patterns, masks email and phone identifiers, enforces output truncation, and integrates with OpenAI moderation models. Diagnostics are exposed through GET /guardrails/diagnostics when enabled.

### Observability and Operations

* Structured JSON logging with correlation identifiers for every request.
* Prometheus metrics covering per-agent request counters, latency histograms, redirect totals, and guardrail violations (gent-workflow/app/observability/metrics.py).
* Readiness and health endpoints that monitor CPU and memory thresholds alongside bootstrapping state.
* Redirect engine that issues human hand-off tickets when guardrails escalate or router confidence is too low.

## Product Strategy and Architectural Decisions

The platform is designed to answer InfinitePay customer questions with predictable behaviour and auditable guardrails. Each decision below clarifies how the component operates and why it exists.

### Intent-guided Multi-agent Orchestration

* **Strategy** ? A central RouterAgent classifies every message and delegates to specialised agents (Knowledge, Support, Custom, Slack) instead of relying on a single general-purpose model.
* **Motivation** ? Splitting responsibilities reduces hallucinations, allows domain-specific tooling (RAG, support policies), and exposes agent-level metrics for tuning.
* **Foundations** ? Single-responsibility design, composite AI pipelines, and enterprise assistant guidance balancing accuracy against cost.

### Retrieval-grounded Responses

* **Strategy** ? KnowledgeAgent v2 combines local index retrieval, heuristic re-ranking, and optional web search to deliver cited answers as the knowledge base evolves.
* **Motivation** ? Pure LLM responses risk misinformation; RAG keeps answers anchored to official pages and supports auditability (links and metadata).
* **Foundations** ? Retrieval-Augmented Generation best practices, 	ext-embedding-3-small vectors, overlapping chunking, and versioned manifests in data/rag/index/.

### Guardrails Before and After the LLM

* **Strategy** ? A safety pipeline normalises text, detects prompt injection, masks PII, and applies automated moderation on every POST /chat request.
* **Motivation** ? Prevents malicious input from manipulating the session, protects sensitive data, and ensures compliance with internal and legal policies.
* **Foundations** ? OWASP conversational AI guidance, OpenAI usage recommendations, and financial-services experience with regulated support flows.

### Deliberate Human Hand-off

* **Strategy** ? SlackAgent confirms user intent, creates tickets, and tracks state in memory. The router redirects when confidence is low or guardrails block the request.
* **Motivation** ? Acknowledging model limits ensures customer issues reach human agents instead of stalling with partial answers.
* **Foundations** ? Contact-centre patterns (FCR and escalation), satisfaction metrics (CSAT), and fail-safe policies.

### End-to-end Observability

* **Strategy** ? Structured logging, Prometheus metrics, propagated correlation_id, and dedicated health endpoints.
* **Motivation** ? Accelerates incident diagnosis, quantifies per-agent latency, and validates ingestion plus guardrail health.
* **Foundations** ? SRE practices, Prometheus telemetry, and readiness probes for resilient deployments.

### Reproducible Operations

* **Strategy** ? Separate Dockerfiles (frontend/backend), Docker Compose for local environments, ingestion scripts with offline modes, and automated tests (pytest, 
pm run build).
* **Motivation** ? Streamlines onboarding, ensures deterministic builds, and provides clear pathways for CI/CD automation.
* **Foundations** ? Infrastructure-as-code, Twelve-Factor principles, and continuous integration with isolated environments.

### Knowledge Evolution

* **Strategy** ? Versioned RAG pipeline with manifests, caches, and ranking heuristics (	itle_boost, exact_term_boost, length_penalty).
* **Motivation** ? Adapts to product changes without re-engineering the backend while preserving history for audits.
* **Foundations** ? Incremental ingestion workflows, deterministic hashing, and metadata-rich manifests stored under data/rag/index/.

## RAG Ingestion Pipeline

The ingestion pipeline crawls InfinitePay public pages (see data/rag/sources/seed_urls.txt) and produces artefacts consumed by the KnowledgeAgent:

1. **Load** ? Crawl whitelisted URLs with configurable depth, timeout, and request pacing.
2. **Clean** ? Strip navigation chrome, deduplicate paragraphs, and hash content for idempotency.
3. **Split** ? Chunk documents with overlap; compute metadata including titles, order, and canonical URLs.
4. **Embed** ? Generate embeddings via OpenAI (	ext-embedding-3-small) and persist them alongside cleaned text.
5. **Index** ? Produce manifest JSONL files, caches, and hashed chunk registries under data/rag/index/.

python scripts/run_rag_dry_run.py executes offline until the split step, while python scripts/run_rag_pipeline.py runs the full pipeline (requires network access and valid OpenAI credentials). The KnowledgeAgent leverages heuristic reranking (	itle_boost, exact_term_boost, length_penalty), query caching with TTL, fallback messaging, and optional web search to satisfy low-recall scenarios.

## Frontend Experience

The React single-page application offers three core surfaces:

* **Chat Console** ? Conversation view with agent-specific styling, clickable citations, correlation IDs, clipboard shortcuts, and localStorage persistence (rontend/src/components/Chat.tsx).
* **Status Page** ? Visualises /health and /readiness payloads, including JSON payload dumps and status indicators (rontend/src/pages/Status.tsx).
* **Metrics Page** ? Streams the raw Prometheus exposition with manual refresh and export-ready formatting (rontend/src/pages/Metrics.tsx).

TailwindCSS powers the visual system, while Vite handles development and production builds.

## Backend-Frontend Interaction and Environment Variables

* The frontend reads VITE_API_BASE_URL (from rontend/.env or build arguments) to reach the FastAPI endpoints.
* The backend enables CORS via FRONTEND_ALLOWED_ORIGINS, which must include the final frontend domain or IP:port.
* When running on VMs or VPS providers (Hostinger, AWS Lightsail, etc.), define complementary variables so both sides point to each other:
  - BACKEND_BASE_URL (optional helper) can be exported to document the public API URL.
  - FRONTEND_ALLOWED_ORIGINS should include https://your-frontend-domain or http://your-ip:5173.
  - VITE_API_BASE_URL must target the backend endpoint (for example https://api.yourdomain.com or http://your-ip:8000).
* Docker images accept runtime variables through docker run -e, docker compose, or .env files, so deployment scripts can inject the correct addresses during container creation.

## Deployment Topologies

| Scenario | Description |
| --- | --- |
| Local development | Run FastAPI with Uvicorn and the React dev server independently. Ideal for rapid iteration and unit testing. |
| Docker Compose | docker compose up --build launches backend and frontend containers on a shared gentnet bridge network, persisting RAG artefacts to ./data. |
| Standalone images | Dockerfile.backend exposes uvicorn app.main:app --host 0.0.0.0 --port 8000, while Dockerfile.frontend bundles the static site behind Nginx on port 80. Suitable for Render, Vercel, or other managed platforms. |

## Deployment Playbooks

### 1. Render (backend) and Vercel (frontend) on free plans

* **Render backend**
  1. Create a Web Service pointing to gent-workflow.
  2. Runtime: Python 3.11+. Start command: uvicorn app.main:app --host 0.0.0.0 --port 8000.
  3. Environment variables: OPENAI_API_KEY, FRONTEND_ALLOWED_ORIGINS=https://your-frontend.vercel.app, METRICS_ENABLED=true, etc.
  4. Configure health check path /health.
* **Vercel frontend**
  1. Import the repository and select the rontend directory.
  2. Framework preset: Vite. Build command 
pm run build, output directory dist.
  3. Environment variables: VITE_API_BASE_URL=https://your-backend.onrender.com.
  4. Deploy and adjust custom domains, keeping CORS aligned on the backend.

### 2. Linux virtual machine (after cloning)

`ash
sudo apt update
sudo apt install -y python3 python3-venv git nodejs npm docker.io docker-compose-plugin

git clone https://github.com/<your-user>/agent-workflow.git
cd agent-workflow

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export OPENAI_API_KEY=sk-...  # optional environment export
export FRONTEND_ALLOWED_ORIGINS="https://your.domain"
uvicorn app.main:app --host 0.0.0.0 --port 8000

cd ../frontend
npm ci
cp .env.example .env
sed -i 's#http://127.0.0.1:8000#http://VM_PUBLIC_IP:8000#' .env
npm run build
npx serve dist --listen 0.0.0.0:4173  # replace with nginx or apache if preferred
`

### 3. Local execution on Linux/Ubuntu

`ash
sudo apt update && sudo apt install -y python3 python3-venv nodejs npm docker.io docker-compose-plugin

# Backend
cd agent-workflow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # populate OPENAI_API_KEY, FRONTEND_ALLOWED_ORIGINS, etc.
uvicorn app.main:app --host 0.0.0.0 --port 8000
`
`ash
# Frontend (separate terminal)
cd frontend
npm ci
cp .env.example .env  # set VITE_API_BASE_URL (e.g. http://localhost:8000)
npm run dev -- --host 0.0.0.0 --port 5173
`

### 4. VPS (Hostinger or similar) using Docker images

`ash
git clone https://github.com/<your-user>/agent-workflow.git
cd agent-workflow
cp .env.example .env  # include FRONTEND_ALLOWED_ORIGINS=https://apps.yourdomain.com

docker build -t agent-backend -f Dockerfile.backend .
docker build -t agent-frontend -f Dockerfile.frontend .

docker run -d --name agent-backend \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e FRONTEND_ALLOWED_ORIGINS="https://apps.yourdomain.com" \
  -e SLACK_ENABLED=false \
  agent-backend

docker run -d --name agent-frontend \
  -p 80:80 \
  -e VITE_API_BASE_URL="https://apps.yourdomain.com:8000" \
  agent-frontend
`

Optional: orchestrate with Docker Compose after exporting the required variables:

`ash
export FRONTEND_ALLOWED_ORIGINS=https://apps.yourdomain.com
export VITE_API_BASE_URL=https://apps.yourdomain.com:8000
docker compose up -d --build
`

## Build and Run Instructions

### Backend (FastAPI)

`ash
cd agent-workflow
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
`

### Frontend (React)

`ash
cd frontend
npm install
cp .env.example .env  # defaults to http://127.0.0.1:8000
npm run dev  # opens http://localhost:5173
`

To produce a distributable bundle, run 
pm run build and optionally 
pm run preview to verify the generated dist/ output.

### Docker Quickstart

`ash
docker compose up --build
`

This builds both images, starts the backend on http://localhost:8000, and serves the frontend via Nginx on http://localhost. Stop the stack with docker compose down (append -v to prune volumes). Individual images can be built with:

`ash
docker build -f Dockerfile.backend -t agent-backend .
docker build -f Dockerfile.frontend -t agent-frontend .
`

## Environment Configuration

Copy .env.example into gent-workflow/.env and tweak grouped settings as needed:

* **OpenAI** ? OPENAI_API_KEY, OPENAI_MODEL, and OPENAI_EMBEDDING_MODEL feed routing and RAG workloads.
* **Retrieval** ? RAG_ENABLED, RAG_TOP_K, RAG_MIN_SCORE, RAG_MAX_CONTEXT_CHARS, RAG_DIAGNOSTICS_ENABLED adjust query behaviour and expose diagnostics.
* **Web search** ? WEB_SEARCH_ENABLED, WEB_SEARCH_PROVIDER, WEB_SEARCH_API_KEY toggle external lookups for out-of-domain questions.
* **Support tooling** ? SUPPORT_FAQ_ENABLED, SUPPORT_FAQ_SCORE_THRESHOLD, SUPPORT_TICKETS_PERSIST_TO_FILE, SUPPORT_ESCALATION_AUTO, SUPPORT_PII_MASKING_ENABLED govern FAQ lookups, ticket persistence, and masking.
* **Guardrails** ? GUARDRAILS_ENABLED, GUARDRAILS_MODE, MAX_INPUT_CHARS, MAX_OUTPUT_CHARS, NORMALIZE_REMOVE_ACCENTS, ANTI_INJECTION_ENABLED, MODERATION_ENABLED enforce safety policies globally.
* **Slack and handoff** ? SLACK_ENABLED, SLACK_MODE, SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN, SLACK_DEFAULT_CHANNEL, HANDOFF_CONFIRM_TTL_SECONDS control the fourth agent that escalates to humans.
* **Observability** ? METRICS_ENABLED, LOG_FORMAT, CORRELATION_ID_HEADER, READINESS_ENABLED, READINESS_CPU_THRESHOLD, READINESS_MEMORY_THRESHOLD_MB wire telemetry and readiness probes.
* **Frontend** ? FRONTEND_ALLOWED_ORIGINS aligns CORS with the deployed frontend, while rontend/.env.example exposes VITE_API_BASE_URL.

All keys ship with conservative defaults so the application boots locally without secrets. When OpenAI credentials are missing, RouterAgent falls back to heuristic routing while KnowledgeAgent continues using cached RAG content.

## Smoke Tests and Collections

* Run the automated end-to-end checks with ./smoke-tests.sh (set BASE_URL when targeting remote deployments). The script validates health, routing, each agent?including Slack confirmation?guardrail blocking, ticket retrieval, metrics, and readiness.
* Import collections/agent-workflow.postman_collection.json into Postman or Insomnia for interactive exploration. The collection mirrors the smoke script and exposes placeholders for ticket identifiers and the backend base URL.

## Support Tooling Deep Dive

SupportService orchestrates four tools to satisfy the challenge requirements:

1. **FAQTool** ? cosine-matched responses sourced from data/support/faq.json (includes boleto and device flows).
2. **TicketTool** ? in-memory or file-backed ticket creation with masked snapshots for GET /support/tickets/{id}.
3. **UserProfileTool** ? extracts and persists user email or plan hints, masks PII, and reuses the data on subsequent interactions.
4. **AccountStatusTool** ? explains operational blocks (for example, blocked transfers) using data/support/account_status.json before escalating to a human.

Metadata returned by the agent lists 	ools_used, the masked profile snapshot, and escalation hints so downstream services can react deterministically.

## RAG Source Catalogue

The ingestion whitelist lives at data/rag/sources/seed_urls.txt and covers every InfinitePay page mandated by the challenge: /maquininha, /maquininha-celular, /tap-to-pay, /pdv, /receba-na-hora, /gestao-de-cobranca, /gestao-de-cobranca-2, /link-de-pagamento, /loja-online, /boleto, /conta-digital, /conta-pj, /pix, /pix-parcelado, /emprestimo, /cartao, and /rendimento.

KnowledgeAgent v2 always emits citations pointing to these URLs (or web search results when explicitly enabled).

## Slack and Handoff Flow

The fourth agent registers pending escalations, requests user confirmation, and pushes formatted payloads to Slack (mock or real mode). Metadata returned from /chat includes the ticket, category, priority, handoff_token, delivery status (ok/ailed/disabled), and latency to ensure compliance teams can audit every hand-off.

## Guardrails and Observability Summary

* Accent stripping, prompt-injection cleansing, PII masking, output truncation, and moderation counters are enforced before and after each agent runs. Violations short-circuit the pipeline with an explicit guardrails response.
* /metrics exposes per-agent request counters, redirect totals, guardrail counters, and latency histograms ready for Prometheus scraping. /readiness validates CPU and memory thresholds and the availability of required credentials, while /health surfaces uptime metadata. Structured JSON logs propagate correlation_id across agents and the Slack client.

## Deployment Readiness

* **Render (backend)** ? Dockerfile.backend bundles the FastAPI app with Uvicorn on port 8000, honours FRONTEND_ALLOWED_ORIGINS, and relies on environment variables only. /health and /readiness are suitable for probe configuration.
* **Vercel (frontend)** ? Dockerfile.frontend ships the Vite build behind Nginx. The project can also use Vercel's "Other" preset with 
pm run build and dist as the output directory. Set VITE_API_BASE_URL to the Render backend URL (or equivalent).

The smoke script and Postman collection double as post-deploy validation steps for both platforms.

## Testing Strategy

* **FastAPI and agents** ? Pytest suite covering health checks, routing logic, guardrails, metrics, persistence, and the RAG admin endpoints (gent-workflow/tests/). OpenAI calls are stubbed for deterministic offline runs.
* **RAG pipeline** ? Unit tests validate chunking, manifest creation, and persistence across the ingestion pipeline.
* **Frontend** ? Manual verification through the Vite dev server; production builds use 
pm run build and can be validated with 
pm run preview.

Execute backend tests with:

`ash
cd agent-workflow
pytest
`

## Challenge Coverage

| Requirement (case proposal) | Implementation |
| --- | --- |
| Three distinct agents orchestrated by a router | RouterAgent dispatches to KnowledgeAgent, CustomerSupportAgent, CustomAgent, and SlackAgent with correlation-aware telemetry. |
| Knowledge agent grounded on InfinitePay content | RAG pipeline ingests the listed URLs and KnowledgeAgent answers with mandatory citations and web-search fallback. |
| Customer support agent with tooling | SupportService wraps FAQ search, ticket management, policy decisions, and escalation prompts, exposing extra metadata for hand-offs. |
| HTTP API entry point | POST /chat accepts { "message": str, "user_id": Optional[str] } and returns JSON with agent, content, citations, and metadata. |
| Dockerisation | Dedicated Dockerfiles and Compose topology orchestrate backend and frontend containers with shared network and persisted data. |
| Testing strategy | Comprehensive pytest suite exercises routing, guardrails, metrics, and RAG components, described in this README and in gent-workflow/README.md. |
| Bonus challenges | SlackAgent handles human hand-off confirmation, Guardrails enforce safe prompting and PII masking, and redirect logic escalates low-confidence routes. |

## Further Enhancements

* Plug an actual Slack API client and ticketing integration in place of the in-memory stubs.
* Expand the frontend with automated tests (Vitest/Testing Library) and screenshot baselines.
* Introduce horizontal scaling guidelines (Redis cache for RAG queries, distributed tracing via OpenTelemetry exporters).
* Extend the RAG whitelist with marketing campaigns while preserving guardrail filters and per-source versioning.

For backend internals and environment variable reference see [gent-workflow/README.md](agent-workflow/README.md).
