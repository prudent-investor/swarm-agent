# Agent Swarm Platform

Plataforma multiagente que integra roteamento inteligente, conhecimento com RAG, suporte automatizado e redirecionamento humano via Slack. Backend em FastAPI (Python) e frontend em React/Vite. Dependencia principal: **OpenAI** (modelos `OPENAI_MODEL` e `OPENAI_EMBEDDING_MODEL`).

## Autor
- Jefferson Rodrigo Schuertz (engenheiro de dados senior e mantenedor do projeto)

## Cobertura de testes
- Comando: `python -m pytest --cov=app --cov-report=term`
- Cobertura de unidade: **86% (28 set 2025 01:40 UTC)**
- Todos os testes unitarios executam offline, com clientes OpenAI simulados

## Estrutura do repositorio
- `agent-workflow/` - backend FastAPI (agents, guardrails, observabilidade, RAG, testes)
- `frontend/` - interface React + Vite
- `smoke-tests.sh` - validacao end-to-end automatizada
- `Dockerfile.backend` / `Dockerfile.frontend` - imagens do backend e frontend
- `docker-compose.yml` - orquestracao local de backend + frontend

## Comunicacao backend <-> frontend
- O frontend usa `VITE_API_BASE_URL` (em `frontend/.env` ou argumento de build) para consumir `POST /chat`, `/route`, `/metrics`, `/health` e outros endpoints
- O backend libera CORS com `FRONTEND_ALLOWED_ORIGINS`
- Em VPS/VM, defina variaveis coerentes para ambos os lados:
  - `BACKEND_EXTERNAL_URL` (sugestao) ou equivalente para documentar a URL publica
  - `FRONTEND_ALLOWED_ORIGINS` incluindo `https://seu-dominio` ou `http://IP:porta`
  - `VITE_API_BASE_URL` apontando para `https://seu-backend` ou `http://IP:8000`
- Variaveis podem ser definidas no build (`docker build --build-arg`) ou na execucao (`docker run -e`, `docker compose`, `.env`)

## Variaveis de ambiente essenciais
| Variavel | Uso |
| --- | --- |
| `OPENAI_API_KEY` | Obrigatoria para RouterAgent e KnowledgeAgent (fallback heuristico ativo quando ausente) |
| `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` | Identificam modelos OpenAI a serem usados |
| `RAG_*` | Parametros de ingestao e recuperacao do RAG |
| `WEB_SEARCH_*` | Habilita busca externa opcional |
| `SUPPORT_*` | Configura ferramentas de suporte (FAQ, tickets, masking) |
| `SLACK_*`, `SLACK_AGENT_ENABLED`, `HANDOFF_CONFIRM_TTL_SECONDS` | Ajustam agente de escalonamento humano |
| `REDIRECT_*` | Limiar para redirecionar mensagens de baixa confianca |
| `METRICS_ENABLED`, `LOG_FORMAT`, `CORRELATION_ID_HEADER` | Telemetria e logs |
| `FRONTEND_ALLOWED_ORIGINS` | Lista de origens autorizadas para CORS |
| `VITE_API_BASE_URL` | URL base da API consumida pelo frontend |

Copie os exemplos antes de iniciar:
```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

## Deploy - tres abordagens

### 1. Execucao local (Linux/Ubuntu)
```bash
sudo apt update && sudo apt install -y python3 python3-venv nodejs npm docker.io docker-compose-plugin

# Backend
cd agent-workflow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # preencha OPENAI_API_KEY, FRONTEND_ALLOWED_ORIGINS, etc.
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
```bash
# Frontend (outro terminal)
cd frontend
npm ci
cp .env.example .env  # configure VITE_API_BASE_URL, ex.: http://localhost:8000
npm run dev -- --host 0.0.0.0 --port 5173
```

### 2. Maquina virtual Linux (apos clonar)
```bash
sudo apt update
sudo apt install -y python3 python3-venv git nodejs npm docker.io docker-compose-plugin

git clone https://github.com/<seu-usuario>/agent-workflow.git
cd agent-workflow

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export OPENAI_API_KEY=sk-...  # opcional
export FRONTEND_ALLOWED_ORIGINS="https://seu.dominio"
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd ../frontend
npm ci
cp .env.example .env
sed -i 's#http://127.0.0.1:8000#http://IP_DA_VM:8000#' .env
npm run build
npx serve dist --listen 0.0.0.0:4173  # pode trocar por nginx/apache
```

### 3. Render (backend) + Vercel (frontend) - planos gratuitos
- Render
  1. Novo Web Service apontando para `agent-workflow`
  2. Runtime Python 3.11+, comando `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  3. Variaveis: `OPENAI_API_KEY`, `FRONTEND_ALLOWED_ORIGINS=https://seu-front.vercel.app`, `METRICS_ENABLED=true`, etc.
  4. Health check em `/health`
- Vercel
  1. Importar projeto e selecionar diretorio `frontend`
  2. Framework Vite, comando `npm run build`, output `dist`
  3. Variaveis: `VITE_API_BASE_URL=https://seu-back.onrender.com`
  4. Deploy e ajuste de dominios conforme necessario

## Deploy em VPS (Hostinger ou similar)
```bash
git clone https://github.com/<seu-usuario>/agent-workflow.git
cd agent-workflow
cp .env.example .env
# ajuste FRONTEND_ALLOWED_ORIGINS=https://apps.seudominio.com

docker build -t agent-backend -f Dockerfile.backend .
docker build -t agent-frontend -f Dockerfile.frontend .

docker run -d --name agent-backend \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e FRONTEND_ALLOWED_ORIGINS="https://apps.seudominio.com" \
  -e SLACK_ENABLED=false \
  agent-backend

docker run -d --name agent-frontend \
  -p 80:80 \
  -e VITE_API_BASE_URL="https://apps.seudominio.com:8000" \
  agent-frontend
```
Opcional: `docker compose up -d --build` configurando `FRONTEND_ALLOWED_ORIGINS` e `VITE_API_BASE_URL` antes do comando (ex.: `export FRONTEND_ALLOWED_ORIGINS=...`).

## Docker (resumo)
```bash
docker build -t agent-backend -f Dockerfile.backend .
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-xxx \
  -e FRONTEND_ALLOWED_ORIGINS="https://front.example.com" agent-backend

docker build -t agent-frontend -f Dockerfile.frontend .
docker run -d -p 8080:80 \
  -e VITE_API_BASE_URL="https://api.example.com" agent-frontend
```

## Smoke tests
```bash
./smoke-tests.sh
BASE_URL=https://api.example.com ./smoke-tests.sh
```

## Dependencias externas
- OpenAI (obrigatoria)
- Slack API (opcional, modo real)

Com essas configuracoes, o projeto roda localmente, em VMs Linux, em VPS (incluindo Hostinger) ou nos planos gratuitos Render + Vercel.
