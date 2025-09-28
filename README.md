# Agent Swarm Platform

A production-ready multi-agent platform that orchestrates router, knowledge, support, and human hand-off agents to answer InfinitePay customer questions. The solution couples a FastAPI backend, a React/Vite frontend, and a Retrieval Augmented Generation (RAG) pipeline that ingests the official InfinitePay website. The stack depends on OpenAI models for routing, retrieval augmentation, and language generation.

## Author
- Jefferson Rodrigo Schuertz (senior data engineer and project maintainer)

## Unit Test Coverage
- Command: `python -m pytest --cov=app --cov-report=term`
- Result: **86% line coverage (28 Sep 2025 01:40 UTC)**

## Repository Structure

```
.
??? agent-workflow/
?   ??? app/
?   ?   ??? agents/            # Router, knowledge, support, custom, and Slack agent implementations
?   ?   ??? core/              # FastAPI bootstrapping, dependency wiring, and shared configuration
?   ?   ??? guardrails/        # Normalisation, moderation, and safety checks for every request
?   ?   ??? observability/     # Structured logging, metrics exporters, and health/readiness probes
?   ?   ??? services/          # LLM, RAG, support tooling, Slack client, and web search helpers
?   ??? data/
?   ?   ??? rag/               # Local vector store artefacts (raw pages, chunks, manifests)
?   ??? scripts/               # RAG ingestion, dry-run, and utility jobs
?   ??? tests/                 # Pytest suites covering agents, guardrails, routers, and APIs
??? app/                       # Standalone scripts for offline RAG experimentation
??? frontend/
?   ??? public/                # Static assets served by Vite
?   ??? src/
?   ?   ??? components/        # Chat UI, status cards, metrics viewers
?   ?   ??? pages/             # Chat, Status, and Metrics routes
?   ?   ??? lib/               # API client, helper hooks, shared utilities
?   ??? tests/                 # Placeholder for future Vitest/RTL suites
??? data/                      # Generated RAG artefacts when running from the repo root
??? scripts/                   # Convenience wrappers around agent-workflow/scripts
??? Dockerfile.backend         # Uvicorn + FastAPI container
??? Dockerfile.frontend        # Nginx + static frontend container
??? docker-compose.yml         # Local topology linking backend and frontend containers
??? requirements.txt           # Backend tooling dependencies
```

### Navigating the Codebase
- Backend lives in `agent-workflow/app/`; start with `main.py`, and explore `agents/`, `guardrails/`, and `observability/` for orchestration and safety layers.
- RAG operations are handled by `agent-workflow/scripts/` and mirrored in top-level `app/` scripts; artefacts land in `data/rag/`.
- Frontend logic sits in `frontend/src/`; configure API access via `frontend/.env` (default `http://127.0.0.1:8000`).
- Deployment assets (Dockerfiles, Compose file, smoke scripts) live at the repository root for fast onboarding.

## Architecture Overview

### Message Topology
1. `POST /chat` passes through Guardrails (prompt-injection filtering, PII masking, moderation, quota checks).
2. `RouterAgent` classifies intent (knowledge, support, custom, Slack). Low-confidence results trigger redirects.
3. Specialised agents generate responses: Knowledge (RAG + citations), Support (tools + policies), Custom (fallback), Slack (human escalation).
4. Responses carry telemetry (`correlation_id`, latency, guardrail flags) exported in `/metrics`.

### Agent Responsibilities
| Agent | Scope | Key Modules |
| --- | --- | --- |
| RouterAgent | Intent detection, OpenAI classification, heuristics fallback, accent normalisation. | `agent-workflow/app/agents/router_agent.py` |
| KnowledgeAgent v2 | Retrieval augmented answers with citations, reranking heuristics, optional web search. | `agent-workflow/app/agents/knowledge_agent_v2.py` |
| CustomerSupportAgent v2 | FAQ, tickets, policies, profile retention, account status, escalation gating. | `agent-workflow/app/agents/support_agent_v2.py`, `agent-workflow/app/services/support_service.py` |
| CustomAgent | Structured fallback replies for out-of-scope conversations. | `agent-workflow/app/agents/custom_agent.py` |
| SlackAgent | Confirmation workflow, Slack payload formatting, retry-aware metrics, pending handoffs. | `agent-workflow/app/agents/slack_agent.py` |

### Guardrails and Safety
- Accent and symbol stripping, prompt-injection detection, PII masking, and moderation enforcement.
- Diagnostics exposed via `GET /guardrails/diagnostics` when enabled.
- Output truncation and masking post-process every response to prevent leakage.

### Observability
- Structured JSON logs with propagated correlation IDs.
- Prometheus metrics per agent, latency histograms, redirect counters, guardrail totals.
- `/health` and `/readiness` endpoints validate uptime, CPU/memory thresholds, and configuration state.

## Backend?Frontend Interaction
- Frontend consumes the API via `VITE_API_BASE_URL` (set in `frontend/.env` or as a Docker build arg).
- Backend whitelists origins with `FRONTEND_ALLOWED_ORIGINS` (comma-separated list of domains or IP:port pairs).
- For VPS/VM setups (Hostinger or similar) define matching variables at runtime:
  - `VITE_API_BASE_URL=https://your-backend.example.com`
  - `FRONTEND_ALLOWED_ORIGINS=https://your-frontend.example.com`
  - Optional helper: `BACKEND_BASE_URL` to document external endpoints for operators
- Docker images respect environment variables supplied with `docker run -e` or `docker compose`.

## Product Strategy and Design Decisions
- **Multi-agent routing** keeps roles focused, reduces hallucination risk, and surfaces agent-level metrics.
- **Retrieval grounding** anchors responses to InfinitePay content (RAG + citations, cached context, web search fallback).
- **Guardrails first and last** ensure prompt-injection resilience, policy compliance, and safe outputs.
- **Human hand-off** via SlackAgent handles low-confidence or escalated cases, preserving audit trails.
- **Observability** delivers actionable telemetry (logs, metrics, readiness) for rapid incident response.
- **Reproducible operations** rely on Docker, Compose, ingestion scripts, and automated tests.
- **Knowledge evolution** uses versioned manifests, ranking heuristics, and cache TTLs to adapt to new content.

## RAG Ingestion Pipeline
1. **Load** ? Crawl URLs listed in `data/rag/sources/seed_urls.txt` with depth, timeout, and pacing controls.
2. **Clean** ? Strip navigation chrome, deduplicate paragraphs, and hash content for idempotency.
3. **Split** ? Chunk documents with overlap, retaining metadata (title, order, URL).
4. **Embed** ? Generate embeddings with `text-embedding-3-small`; persist alongside cleaned text.
5. **Index** ? Produce manifest JSONL files and caches under `data/rag/index/` for KnowledgeAgent consumption.

Run `python scripts/run_rag_dry_run.py` for an offline pipeline up to the split step, or `python scripts/run_rag_pipeline.py` for the full ingestion (requires OpenAI credentials and network access).

## Frontend Experience
- **Chat Console** (`frontend/src/components/Chat.tsx`) shows agent-tagged dialogue with citations and clipboard helpers.
- **Status Page** (`frontend/src/pages/Status.tsx`) surfaces `/health` and `/readiness` payloads.
- **Metrics Page** (`frontend/src/pages/Metrics.tsx`) streams Prometheus output with export-ready formatting.

## Deployment Playbooks

### Local Development (Linux/Ubuntu)
```bash
sudo apt update && sudo apt install -y python3 python3-venv nodejs npm docker.io docker-compose-plugin

# Backend
cd agent-workflow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
```bash
# Frontend (separate terminal)
cd frontend
npm ci
cp .env.example .env
npm run dev -- --host 0.0.0.0 --port 5173
```

### Linux Virtual Machine (after cloning)
```bash
sudo apt update
sudo apt install -y python3 python3-venv git nodejs npm docker.io docker-compose-plugin

git clone https://github.com/<your-user>/swarm-agent.git
cd swarm-agent/agent-workflow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export OPENAI_API_KEY=sk-...
export FRONTEND_ALLOWED_ORIGINS="https://your.domain"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
```bash
# Frontend on the VM
cd ../frontend
npm ci
cp .env.example .env
sed -i 's#http://127.0.0.1:8000#http://VM_PUBLIC_IP:8000#' .env
npm run build
npx serve dist --listen 0.0.0.0:4173
```

### Render (backend) + Vercel (frontend)
- **Render**: Web Service, Python 3.11+, command `uvicorn app.main:app --host 0.0.0.0 --port 8000`, env vars (`OPENAI_API_KEY`, `FRONTEND_ALLOWED_ORIGINS`, `METRICS_ENABLED=true`), health probe `/health`.
- **Vercel**: Project rooted at `frontend`, framework preset Vite, build `npm run build`, output `dist`, env var `VITE_API_BASE_URL=https://your-backend.onrender.com`.

### VPS (Hostinger or similar) using Docker Images
```bash
git clone https://github.com/<your-user>/swarm-agent.git
cd swarm-agent
cp .env.example .env

# Build images
docker build -t agent-backend -f Dockerfile.backend .
docker build -t agent-frontend -f Dockerfile.frontend .

# Run backend
docker run -d --name agent-backend \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e FRONTEND_ALLOWED_ORIGINS="https://apps.yourdomain.com" \
  -e SLACK_ENABLED=false \
  agent-backend

# Run frontend
docker run -d --name agent-frontend \
  -p 80:80 \
  -e VITE_API_BASE_URL="https://apps.yourdomain.com:8000" \
  agent-frontend
```
Optional orchestration:
```bash
export FRONTEND_ALLOWED_ORIGINS=https://apps.yourdomain.com
export VITE_API_BASE_URL=https://apps.yourdomain.com:8000
docker compose up -d --build
```

## Build and Run (Quick Reference)
- Backend: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload`
- Frontend: `npm install && npm run dev`
- Docker Compose: `docker compose up --build`
- Individual images: `docker build -f Dockerfile.backend -t agent-backend .` (and counterpart for frontend)

## Environment Configuration
Copy `.env.example` to `agent-workflow/.env` and adjust groups:
- **OpenAI**: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`
- **Retrieval**: `RAG_ENABLED`, `RAG_TOP_K`, `RAG_MIN_SCORE`, `RAG_MAX_CONTEXT_CHARS`, `RAG_DIAGNOSTICS_ENABLED`
- **Web Search**: `WEB_SEARCH_ENABLED`, `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_API_KEY`
- **Support Tools**: `SUPPORT_FAQ_ENABLED`, `SUPPORT_FAQ_SCORE_THRESHOLD`, `SUPPORT_TICKETS_PERSIST_TO_FILE`, `SUPPORT_ESCALATION_AUTO`, `SUPPORT_PII_MASKING_ENABLED`
- **Guardrails**: `GUARDRAILS_ENABLED`, `GUARDRAILS_MODE`, `MAX_INPUT_CHARS`, `MAX_OUTPUT_CHARS`, `NORMALIZE_REMOVE_ACCENTS`, `ANTI_INJECTION_ENABLED`, `MODERATION_ENABLED`
- **Slack/Handoff**: `SLACK_ENABLED`, `SLACK_MODE`, `SLACK_WEBHOOK_URL` or `SLACK_BOT_TOKEN`, `SLACK_DEFAULT_CHANNEL`, `HANDOFF_CONFIRM_TTL_SECONDS`
- **Observability**: `METRICS_ENABLED`, `LOG_FORMAT`, `CORRELATION_ID_HEADER`, `READINESS_ENABLED`, `READINESS_CPU_THRESHOLD`, `READINESS_MEMORY_THRESHOLD_MB`
- **Frontend**: `FRONTEND_ALLOWED_ORIGINS` plus `frontend/.env` for `VITE_API_BASE_URL`

## Smoke Tests and Collections
- Run `./smoke-tests.sh` locally (default `BASE_URL=http://localhost:8000`) or point to remote deployments (`BASE_URL=https://api.example.com ./smoke-tests.sh`).
- Import `collections/agent-workflow.postman_collection.json` into Postman/Insomnia for manual exploration.

## Support Tooling Detail
1. **FAQTool** ? cosine-matched answers sourced from `data/support/faq.json` (includes boleto/device flows).
2. **TicketTool** ? In-memory or file-backed ticket creation with masked snapshots for `GET /support/tickets/{id}`.
3. **UserProfileTool** ? Extracts user metadata, masks PII, and reuses profiles across sessions.
4. **AccountStatusTool** ? Provides explanations for blocked transfers or limits before escalation.

Metadata emitted by SupportAgent includes `tools_used`, masked profile information, ticket details, and escalation hints.

## RAG Source Catalogue
`data/rag/sources/seed_urls.txt` lists every required InfinitePay page (`/maquininha`, `/maquininha-celular`, `/tap-to-pay`, `/pdv`, `/receba-na-hora`, `/gestao-de-cobranca`, `/gestao-de-cobranca-2`, `/link-de-pagamento`, `/loja-online`, `/boleto`, `/conta-digital`, `/conta-pj`, `/pix`, `/pix-parcelado`, `/emprestimo`, `/cartao`, `/rendimento`). KnowledgeAgent v2 always cites these resources (or external search results when enabled).

## Slack and Handoff Flow
SlackAgent records pending escalations, requests user confirmation, and sends formatted payloads (mock or real) to Slack. Responses from `/chat` carry `ticket_id`, `category`, `priority`, `handoff_token`, delivery status (`ok`, `failed`, `disabled`), and latency metrics.

## Guardrails and Observability Summary
- Guardrails enforce accent stripping, prompt-injection cleansing, masking, moderation, and truncation before/after every agent call.
- `/metrics` surfaces per-agent counters and guardrail totals; `/readiness` validates runtime health; `/health` exposes uptime metadata.

## Deployment Readiness
- **Render backend**: Deploy with `Dockerfile.backend`; configure `FRONTEND_ALLOWED_ORIGINS`; rely on `/health` and `/readiness` probes.
- **Vercel frontend**: Deploy with `Dockerfile.frontend` or Vercel preset; set `VITE_API_BASE_URL` to the backend URL.

## Testing Strategy
- Backend/agents: `pytest` suite covers routing, guardrails, metrics, RAG endpoints.
- RAG modules: unit tests validate chunking, manifests, and persistence.
- Frontend: manual validation via `npm run dev`; production builds verified with `npm run build` and `npm run preview`.

Run backend tests with:
```bash
cd agent-workflow
pytest
```

## Challenge Coverage
| Requirement | Implementation |
| --- | --- |
| Multi-agent router | RouterAgent dispatches to knowledge, support, custom, and Slack agents with telemetry. |
| Knowledge grounding | RAG pipeline ingests InfinitePay URLs; KnowledgeAgent returns cited answers and web-search fallbacks. |
| Support tooling | SupportService combines FAQ, ticketing, policies, and escalation metadata. |
| HTTP API | `POST /chat` delivers structured JSON responses with agent metadata. |
| Containerisation | Dedicated Dockerfiles and Compose topology for backend and frontend. |
| Testing | Comprehensive pytest coverage described in this README and `agent-workflow/README.md`. |
| Bonus items | Slack hand-off flow, global guardrails, redirect logic for low-confidence cases. |

## Further Enhancements
- Integrate a production Slack client and ticketing system.
- Add automated frontend tests (Vitest/RTL) and visual regression checks.
- Provide horizontal scaling guidance (Redis cache, distributed tracing with OpenTelemetry).
- Extend RAG whitelist for future marketing content while keeping guardrails intact.

See [`agent-workflow/README.md`](agent-workflow/README.md) for backend internals and an expanded environment variable reference.
