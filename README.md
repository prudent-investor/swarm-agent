# Agent Workflow

## Estrutura de Diretorios
```
agent-workflow/
|-- app/
|   |-- __init__.py
|   |-- main.py
|   |-- agents/
|   |   |-- __init__.py
|   |   |-- base.py
|   |   `-- router_agent.py
|   |-- routers/
|   |   |-- __init__.py
|   |   |-- health.py
|   |   `-- router_agent.py
|   |-- settings.py
|   `-- utils/
|       |-- __init__.py
|       `-- runtime.py
|-- tests/
|   |-- test_health.py
|   `-- test_router_agent.py
|-- .env.example
|-- .gitignore
|-- README.md
`-- requirements.txt
```

## Preparacao do Ambiente
1. Crie o ambiente virtual: `python -m venv .venv`
2. Ative o ambiente virtual:
   - PowerShell: `.\.venv\Scripts\Activate.ps1`
   - CMD: `.\.venv\Scripts\activate.bat`
   - Unix/macOS: `source .venv/bin/activate`
3. Instale as dependencias: `pip install -r requirements.txt`

## Configuracao
1. Copie o arquivo de exemplo: `cp .env.example .env` (ou `copy .env.example .env` no Windows)
2. Ajuste os valores conforme necessario.

## Executando a Aplicacao
1. Inicie o servidor: `uvicorn app.main:app --reload`
2. Acesse a documentacao interativa em `http://127.0.0.1:8000/docs`
3. Consulte o healthcheck em `http://127.0.0.1:8000/health`

### Saida Esperada (`GET /health`)
```json
{
  "status": "ok",
  "app": "Agent Workflow",
  "version": "0.1.0",
  "uptime_seconds": 0.123
}
```

## Etapa 2: Router Agent
- O Router Agent recebe uma mensagem e classifica a intencao em `knowledge`, `support` ou `custom` usando um modelo da OpenAI.
- O endpoint de validacao esta disponivel em `POST /route` e espera um corpo JSON no formato `{"message": "texto aqui"}`.
- Exemplo de requisicao:
  ```bash
  curl -X POST http://127.0.0.1:8000/route \
       -H "Content-Type: application/json" \
       -d '{"message": "Como funciona a politica de privacidade?"}'
  ```
- Exemplo de resposta:
  ```json
  {
    "route": "knowledge",
    "hint": "Refer to docs"
  }
  ```
- Em producao o OpenAI API sera chamado com a chave e o modelo definidos nas variaveis de ambiente. Nos testes utilizamos um mock para evitar chamadas externas.

## Testes Automatizados
- Rode os testes com `pytest`
- Os testes do router cobrem as tres rotas esperadas com mensagens de exemplo utilizando o endpoint `/route`.

## Variaveis de Ambiente
- `APP_NAME`: nome exibido na API (padrao: Agent Workflow)
- `APP_VERSION`: versao reportada no healthcheck (padrao: 0.1.0)
- `APP_PORT`: porta utilizada pelo servidor (padrao: 8000)
- `OPENAI_API_KEY`: chave da API da OpenAI utilizada pelo Router Agent
- `OPENAI_MODEL`: modelo da OpenAI (padrao: gpt-4o-mini)

## Proximos Passos
- Implementar o agente Knowledge para buscar informacoes em fontes de apoio.

## Atividades Manuais Sugeridas
- Inicializar o repositorio Git e criar commits conforme a evolucao do projeto.
- Criar e ativar o ambiente virtual do Python, instalando as dependencias listadas.
- Copiar `.env.example` para `.env` e ajustar valores conforme necessario.
- Subir o servidor localmente com Uvicorn e validar os endpoints `/health` e `/route`.
- Executar `pytest` para confirmar o funcionamento do healthcheck e do router.
## Etapa 7 - Slack Agent (handoff humano)

## Etapa 11 — Interface Web Customizada
- Frontend moderno em React + Vite + TypeScript na pasta `frontend/`, estilizado com TailwindCSS e tema azul/dourado exclusivo.
- Consome os endpoints existentes (`/chat`, `/route`, `/health`, `/readiness`, `/metrics`), exibindo citações clicáveis, ID de correlação e diferenciação por agente.
- Persistência local do histórico (localStorage), botão "Novo Chat", ação "Copiar resposta" e spinner enquanto aguarda o backend.
- Páginas adicionais: **Status** (health/readiness) e **Metrics** (export Prometheus).

### Como executar
1. `cd frontend`
2. `npm install`
3. Copie `.env.example` para `.env` e ajuste `VITE_API_BASE_URL` (padrão `http://127.0.0.1:8000`).
4. `npm run dev` → acesse `http://localhost:5173`.

### Build / Deploy
- `npm run build` gera `dist/` pronto para Vercel, Netlify ou qualquer CDN estática (`npm run preview` para validar a build).
- Ajuste `FRONTEND_ALLOWED_ORIGINS` no backend para liberar o domínio do frontend.
- **Quando aciona**: o SupportAgent v2 sinaliza escalation_suggested=true ou o usuario pede explicitamente um humano; o sistema registra pedido no HandoffFlow e pergunta: “Posso acionar suporte humano no Slack? Responda ‘sim’ para confirmar.”
- **Confirmacao obrigatoria**: respostas afirmativas (sim, pode, “quero falar com humano” etc.) aciona o SlackAgent; negativas cancelam o pedido e mensagens ambiguas geram um novo lembrete curto.
- **Validacao manual**: 1) enviar caso critico em /chat ? resposta pede confirmacao ? responder sim com handoff_token ? meta retorna handoff_status="ok" e handoff_message_id; 2) enviar “Quero falar com humano” ? confirmacao ? SlackAgent executa; acompanhar logs slack.handoff.* sem PII.

## Etapa 12 — Containerização e Deploy

A etapa 12 empacota todo o ecossistema (FastAPI + agentes + observabilidade + frontend React) em contêineres prontos para desenvolvimento local com Docker Compose e deploy em serviços gerenciados como Render, Vercel ou Netlify.

### Pré-requisitos

- Docker e Docker Compose instalados.
- Arquivo de variáveis do backend pronto: copie `agent-workflow/.env.example` para `agent-workflow/.env` e ajuste as chaves (ex.: `OPENAI_API_KEY`).
- (Opcional) Arquivo `.env` para o frontend com `VITE_API_BASE_URL` caso deseje builds fora do Compose.

### Build das imagens individuais

```bash
docker build -f Dockerfile.backend -t agent-backend .
docker build -f Dockerfile.frontend -t agent-frontend .
```

As imagens acima executam o backend via `uvicorn app.main:app` na porta `8000` e servem o bundle estático do frontend por Nginx na porta `80`.

### Executando tudo com Docker Compose

```bash
docker compose up --build
```

- Backend disponível em `http://localhost:8000/health`.
- Frontend servido em `http://localhost` (mapeado para a porta 80 do contêiner Nginx).
- Os serviços compartilham a rede interna `agentnet`, permitindo que o frontend use `http://backend:8000` como base (`VITE_API_BASE_URL`).
- O volume `./data:/app/agent-workflow/data` mantém arquivos de suporte gerados pelo backend durante o desenvolvimento.

Quando terminar, execute `docker compose down` para encerrar e `docker compose down -v` se quiser remover volumes.

### Deploy do backend (Render)

1. Crie um novo serviço **Web Service** no Render, apontando para este repositório.
2. Escolha a opção **Docker** e informe `Dockerfile.backend` como arquivo da imagem.
3. Defina o comando padrão como `uvicorn app.main:app --host 0.0.0.0 --port 8000` (Render detecta automaticamente, mas deixe explícito se preferir).
4. Configure as variáveis de ambiente no painel (ou faça upload do arquivo `.env` via Secrets Manager).
5. Após o deploy, valide `https://<seu-servico>.onrender.com/health` para garantir que o backend respondeu `status: ok`.

### Deploy do frontend (Vercel/Netlify ou contêiner único)

**Vercel / Netlify (build estática):**

1. Crie um novo projeto apontando para a pasta `frontend/`.
2. Configure as variáveis de ambiente de build com `VITE_API_BASE_URL=https://<backend-publico>`.
3. Use o comando de build padrão `npm run build` (Vercel/Netlify já inferem automaticamente).
4. Após a publicação, acesse o domínio gerado e valide a interface (a página **Status** deve consumir o endpoint `/health` do backend público).

**Alternativa (contêiner único):**

- Em um servidor próprio, basta rodar `docker compose up -d` e expor as portas 80 (frontend) e 8000 (backend) conforme necessário. Ajuste `FRONTEND_ALLOWED_ORIGINS` no backend para incluir o domínio externo que irá servir o frontend.

### Checklist pós-deploy

- ✅ Backend responde `GET /health` com `status: ok`.
- ✅ Frontend carrega e utiliza o backend para `/chat`, `/status` e `/metrics`.
- ✅ Logs e métricas continuam disponíveis conforme configurado nas etapas anteriores.
ailed, latencia media/p95).
- **Guardrails**: nada de PII crua; logs trazem apenas message_id, channel, correlation_id; erros retornam handoff_status="failed" sem detalhar excecoes; com Slack desabilitado o agente responde handoff_status="disabled" de forma cordial.
- **Metadados do /chat**: handoff_channel, handoff_status, handoff_message_id, handoff_token, 	icket_id, category, priority e handoff_request (token + expiracao) quando aguardando confirmacao.
- **Variaveis**: SLACK_ENABLED, SLACK_MODE (mock|eal), SLACK_WEBHOOK_URL/SLACK_BOT_TOKEN, SLACK_DEFAULT_CHANNEL, SLACK_TIMEOUT_SECONDS, SLACK_MAX_RETRIES, HANDOFF_CONFIRM_TTL_SECONDS, HANDOFF_SUMMARY_MAX_CHARS, HANDOFF_DETAILS_MAX_CHARS, PII_MASKING_ENABLED.
- **Testes**: pytest -k slack_agent cobre mascaramento, cliente mock, confirmacao/desabilitado e fluxo integradao (	ests/test_slack_agent_unit.py, 	ests/test_slack_agent_integration.py).
- **Validacao manual**: 1) enviar caso critico em /chat ? resposta pede confirmacao ? responder sim com handoff_token ? meta retorna handoff_status="ok" e handoff_message_id; 2) enviar “Quero falar com humano” ? confirmacao ? SlackAgent executa; acompanhar logs slack.handoff.* sem PII.
