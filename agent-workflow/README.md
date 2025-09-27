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
|   |   |-- custom_agent.py
|   |   |-- knowledge_agent.py
|   |   |-- router_agent.py
|   |   `-- support_agent.py
|   |-- rag/
|   |   |-- __init__.py
|   |   |-- cleaner.py
|   |   |-- config.py
|   |   |-- embedder.py
|   |   |-- indexer.py
|   |   |-- loader.py
|   |   |-- persistence.py
|   |   |-- runner.py
|   |   `-- splitter.py
|   |-- routers/
|   |   |-- __init__.py
|   |   |-- chat.py
|   |   |-- health.py
|   |   |-- rag_admin.py (opcional, habilitado via ENV)
|   |   `-- router_agent.py
|   |-- schemas/
|   |   |-- __init__.py
|   |   `-- chat.py
|   |-- services/
|   |   |-- __init__.py
|   |   `-- llm_provider.py
|   |-- settings.py
|   `-- utils/
|       |-- __init__.py
|       `-- runtime.py
|-- data/
|   `-- rag/
|       |-- chunks/
|       |-- index/
|       |-- raw/
|       `-- sources/
|           |-- seed_urls.txt
|           `-- whitelist.txt
|-- scripts/
|   |-- run_rag_dry_run.py
|   `-- run_rag_pipeline.py
|-- tests/
|   |-- test_admin_rag_endpoint.py
|   |-- test_agents_v1.py
|   |-- test_chat_endpoint.py
|   |-- test_health.py
|   |-- test_persistence.py
|   |-- test_rag_runner.py
|   |-- test_router_agent.py
|   `-- test_splitter.py
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
1. Copie o arquivo de exemplo: `cp .env.example .env` (ou `copy .env.example .env` no Windows).
2. Preencha `OPENAI_API_KEY` com uma chave valida, ajuste `OPENAI_MODEL` e `OPENAI_EMBEDDING_MODEL` se necessario.
3. Configure limites do RAG conforme necessidade (maximo de paginas, timeout, intervalo entre requisicoes, tamanho dos chunks).

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
- O Router Agent classifica a mensagem em `knowledge`, `support` ou `custom` utilizando um modelo da OpenAI.
- Endpoint: `POST /route` com corpo `{"message": "texto aqui"}`.
- Em producao o roteador consulta a API da OpenAI; nos testes usamos mock.

## Etapa 3  Agents v1 (Knowledge, Support, Custom)
- Endpoint: `POST /chat` com `message` (obrigatorio), `user_id` (opcional) e `metadata` (opcional).
- Roteador decide a rota e dispara o agente correspondente:
  - `KnowledgeAgent v1`: responde perguntas gerais (sem RAG ainda).
  - `CustomerSupportAgent v1`: coleta informacoes basicas para suporte humano.
  - `CustomAgent v1`: responde mensagens fora do escopo principal.
- Resposta padronizada inclui `agent`, `content`, `citations` (lista), `meta` (rota + latencia) e `correlation_id`.
- Logs registram inicio/fim do atendimento e contadores acompanham volume por agente.

## Etapa 4  RAG: Ingestao e Indexacao
- Pipeline coleta conteudo das URLs listadas em `data/rag/sources/seed_urls.txt` respeitando o whitelist (`data/rag/sources/whitelist.txt`).
- Fases: load (download das paginas) -> clean (texto principal) -> split (chunking com sobreposicao) -> embed (OpenAI Embeddings) -> index (JSONL simples) -> manifest.
- Diretorios de saida:
  - Brutos: `data/rag/raw` (JSONL por execucao).
  - Chunks: `data/rag/chunks` (antes/depois de embedding).
  - Indice + manifest: `data/rag/index`.
- Scripts:
  - `python scripts/run_rag_pipeline.py` (suporta `--dry-run`).
  - `python scripts/run_rag_dry_run.py` (dry-run direto, sem HTTP nem embeddings).
- Endpoint administrativo opcional: habilite `RAG_ADMIN_ENABLED=true` no `.env`. Quando ativo, o router expe `POST /rag/reindex`.
  - Corpo: `{"confirm": true, "dry_run": false}`. O campo `confirm` precisa ser `true` para evitar acionamento acidental.
  - Resposta traz contagens de paginas, chunks e itens indexados.
  - Em ambientes de teste, o endpoint pode ser mantido desligado (`false`) para nao aparecer.
- Artefatos: cada execucao gera manifest (`manifest_<run_id>.json`) com metricas agregadas e timestamp.
- Dry-run executa ate `clean + split`, sem rede nem embeddings (util para testes e validacao rapida).
- Boas praticas adotadas: whitelist rigida, limite de paginas/profundidade, timeout configuravel, intervalo entre requisicoes, deduplicacao por hash e ignorar chunks vazios.
- Proximas etapas integrarao o indice ao `KnowledgeAgent` para respostas com citacoes.

## Testes Automatizados
- Rode `pytest` para executar toda a suite (agents, router, RAG pipeline, endpoint admin).
- Testes de RAG usam mocks/stubs, nao acessam rede nem OpenAI real.

## Variaveis de Ambiente
- `APP_NAME`: nome exibido na API (padrao: Agent Workflow)
- `APP_VERSION`: versao reportada no healthcheck (padrao: 0.1.0)
- `APP_PORT`: porta utilizada pelo servidor (padrao: 8000)
- `OPENAI_API_KEY`: chave da API da OpenAI utilizada pelos agentes e provider
- `OPENAI_MODEL`: modelo de chat para os agentes (ex.: gpt-4.1-mini)
- `OPENAI_EMBEDDING_MODEL`: modelo de embedding para o RAG (ex.: text-embedding-3-small)
- `RAG_ADMIN_ENABLED`: habilita (`true`) ou desabilita (`false`) o endpoint `/rag/reindex`
- `RAG_MAX_PAGES`, `RAG_MAX_DEPTH`: limites de crawling
- `RAG_REQUEST_TIMEOUT`, `RAG_REQUEST_INTERVAL`: timeout e intervalo entre requisicoes
- `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`: parametros de chunking
- `REDIRECT_ENABLED`: ativa o mecanismo de redirecionamento automatico para humanos (padrao: true)
- `REDIRECT_CONFIDENCE_THRESHOLD`: limiar minimo de confianca do roteador antes de acionar redirect (padrao: 0.3)
- `GUARDRAILS_REDIRECT_ALWAYS`: quando true, toda conversa e encaminhada a humanos independentemente da confianca
- `SLACK_AGENT_ENABLED`: habilita o agente de escalonamento humano simulado (padrao: true)
- `SLACK_CHANNEL_DEFAULT`: canal destino utilizado pelo SlackAgent mock (padrao: support-humans)
- `METRICS_ENABLED`: habilita o endpoint `/metrics` e a coleta de contadores/histogramas (padrao: true)
- `LOG_FORMAT`: `json` (padrao) para logs estruturados ou `text` para formato legivel
- `CORRELATION_ID_HEADER`: cabecalho utilizado para propagar correlation-id (padrao: X-Correlation-ID)
- `READINESS_ENABLED`: habilita o endpoint `/readiness` (padrao: true)
- `READINESS_CPU_THRESHOLD`: limite maximo de uso de CPU em porcentagem antes de sinalizar indisponibilidade (padrao: 90)
- `READINESS_MEMORY_THRESHOLD_MB`: limite maximo de memoria em MB antes de sinalizar indisponibilidade (padrao: 1024)

## Proximos Passos
- Etapa 5: conectar o KnowledgeAgent ao indice para recuperar contexto (RAG completo) e retornar citacoes.

## Atividades Manuais Sugeridas
- Inicializar o repositorio Git e registrar commits conforme a evolucao do projeto.
- Criar/ativar o ambiente virtual, instalar dependencias e preencher `.env`.
- Rodar `pytest` para validar a base.
- Executar `python scripts/run_rag_dry_run.py` para inspecionar chunking.
- Executar `python scripts/run_rag_pipeline.py` para produzir embeddings e indice completos (requer internet e creditos OpenAI).
- Se desejar acionar via API, habilitar `RAG_ADMIN_ENABLED=true` e chamar `POST /rag/reindex` com `{"confirm": true}`.

## Etapa 5 - Knowledge Agent v2 (RAG com citacoes)
- Fluxo: consulta do usuario -> retriever le o indice -> heuristica de re-rank -> filtros anti prompt-injection -> construcao de contexto -> chamada ao LLM -> resposta curta com citacoes obrigatorias.
- Fontes oficiais priorizadas (usadas como base e citadas sempre que o conteudo for utilizado):
  - https://www.infinitepay.io
  - https://www.infinitepay.io/maquininha
  - https://www.infinitepay.io/maquininha-celular
  - https://www.infinitepay.io/tap-to-pay
  - https://www.infinitepay.io/pdv
  - https://www.infinitepay.io/receba-na-hora
  - https://www.infinitepay.io/gestao-de-cobranca-2
  - https://www.infinitepay.io/gestao-de-cobranca
  - https://www.infinitepay.io/link-de-pagamento
  - https://www.infinitepay.io/loja-online
  - https://www.infinitepay.io/boleto
  - https://www.infinitepay.io/conta-digital
  - https://www.infinitepay.io/conta-pj
  - https://www.infinitepay.io/pix
  - https://www.infinitepay.io/pix-parcelado
  - https://www.infinitepay.io/emprestimo
  - https://www.infinitepay.io/cartao
  - https://www.infinitepay.io/rendimento
- KnowledgeAgent v2 usa o indice local, aplica re-rank configuravel (`RAG_RERANK_*`), filtros de seguranca e monta um contexto enxuto antes de chamar o LLM. Respostas trazem meta `rag_used`, `top_k_selected`, `avg_score`, `cache_hit`, `fallback_used`, `web_search_used`, `latency_ms` e `citations` sempre preenchido.
- Cache leve com TTL (`RAG_CACHE_TTL_SECONDS`) evita recomputar retrieval para a mesma pergunta.
- Fallback: se o indice estiver vazio ou abaixo do limiar (`RAG_MIN_SCORE`), o agente responde honestamente que nao encontrou evidencias e cita pelo menos a raiz da InfinitePay. Com `WEB_SEARCH_ENABLED=true`, o agente pode complementar com web search (citacoes marcadas como `source_type=external`).
- Endpoint de diagnostico opcional (`RAG_DIAGNOSTICS_ENABLED=true`): `POST /rag/diagnostics` retorna top-k bruto, pos re-rank, chunks selecionados e citacoes util para depuracao.
- Seguranca: filtros removem trechos com instrucoes maliciosas e elementos de navegacao; o LLM e instruido a nao inventar fatos sem fonte.

### Configuracoes especificas do Knowledge Agent v2
- `RAG_ENABLED`, `RAG_TOP_K`, `RAG_MAX_CONTEXT_CHARS`, `RAG_MIN_SCORE`: controlam retrieval e volume de contexto.
- `RAG_RERANK_TITLE_BOOST`, `RAG_RERANK_EXACT_TERM_BOOST`, `RAG_RERANK_LENGTH_PENALTY`: pesos da heuristica de re-rank.
- `RAG_CACHE_TTL_SECONDS`: TTL em segundos para o cache de queries.
- `RAG_DIAGNOSTICS_ENABLED`: habilita o endpoint de diagnostico.
- `WEB_SEARCH_ENABLED`, `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_API_KEY`: ativam integracoes externas (opcional).

### Interpretando o campo meta
- `rag_used`: indica se o RAG foi utilizado de fato.
- `top_k_selected`: quantidade de chunks mantidos no contexto final.
- `avg_score`: media dos scores apos re-rank.
- `cache_hit`: consulta atendida pelo cache.
- `fallback_used`: resposta de fallback (sem contexto suficiente).
- `web_search_used`: consumo de fonte externa.
- `latency_ms`: tempo total do agente.

### Comportamentos de contorno
- Sem indice ou sem resultados uteis -> resposta honesta + citations com a raiz da InfinitePay.
- Falha do LLM -> erro controlado (503).
- Prompt-injection detectado -> chunk descartado antes de montar o contexto.
## Etapa 6 - Customer Support v2 (FAQ + Ticket + Escalonamento)
- Fluxo principal: mensagem normalizada -> busca deterministica na FAQ (`data/support/faq.json`); se `score >= SUPPORT_FAQ_SCORE_THRESHOLD`, responde direto com justificativa; caso contrario `SupportService` cria ticket (`TicketTool`) e aplica `support_policies.py` para categoria, prioridade e escalonamento.
- Dataset da FAQ: arquivo versionado `data/support/faq.json` com campos `id`, `pergunta`, `resposta`, `tags`, `categoria`, `atualizado_em`. Use `FAQTool.reload()` para recarregar em memoria apos edicoes.
- Tickets: armazenamento em memoria com persistencia atomica opcional em `data/support/tickets.json` (`SUPPORT_TICKETS_PERSIST_TO_FILE=true`). IDs legiveis (`SUP-<data>-<sufixo>`), status, prioridade, categoria, resumo, descricao, timestamps UTC, flag de escalonamento e notas internas (privadas).
- Politicas e guardrails: `support_policies.py` mapeia palavras-chave para categorias/prioridades; termos criticos, repeticao ou pedido explicito de humano aciona escalonamento. Logs e respostas publicas mascaram PII (`user_ref`), e o agente respeita `SUPPORT_MAX_RESPONSE_CHARS` sem pedir dados sensiveis.
- Telemetria: logs estruturados (`support.start`, `support.faq_hit`, `support.ticket_created`, `support.finish`, `support.ticket_lookup.*`) com `correlation_id`. Metricas em memoria acompanham contadores de FAQ/tickets/escalonamentos e latencias (media, p95).
- Endpoint publico: GET /support/tickets/{ticket_id} retorna TicketPublicResponse (status, datas, prioridade, categoria, resumo, user_ref mascarado). Quando inexistente, responde 404 {"error":"ticket_not_found"}.
- Variaveis de ambiente: `SUPPORT_FAQ_ENABLED`, `SUPPORT_FAQ_SCORE_THRESHOLD`, `SUPPORT_TICKETS_PERSIST_TO_FILE`, `SUPPORT_TICKETS_FILE_PATH`, `SUPPORT_ESCALATION_AUTO`, `SUPPORT_PII_MASKING_ENABLED`, `SUPPORT_MAX_RESPONSE_CHARS`, `SUPPORT_CATEGORY_TERMS_OVERRIDES`, `SUPPORT_SEVERITY_TERMS_OVERRIDES`.
- Testes: `pytest -k support` cobre os cenarios desta etapa (FAQ tool, ticket tool, politicas, agente completo e endpoint publico).
- Validacao manual: `POST /chat` com mensagens de senha vs. dispositivo para observar FAQ vs. ticket + escalonamento; consultar `GET /support/tickets/<id>` com `X-Correlation-ID` para inspecionar logs e mascaramento.
- `SUPPORT_FAQ_ENABLED`: ativa/desativa a ferramenta de FAQ (padrao: true)
- `SUPPORT_FAQ_SCORE_THRESHOLD`: limiar minimo de score para considerar resposta da FAQ (padrao: 0.65)
- `SUPPORT_TICKETS_PERSIST_TO_FILE`: grava tickets em `SUPPORT_TICKETS_FILE_PATH` usando escrita atomica (padrao: false)
- `SUPPORT_TICKETS_FILE_PATH`: caminho do JSON de tickets quando persistencia estiver habilitada (padrao: data/support/tickets.json)
- `SUPPORT_ESCALATION_AUTO`: forÃ§a escalonamento para prioridades alta/critica automaticamente (padrao: false)
- `SUPPORT_PII_MASKING_ENABLED`: liga/desliga mascaramento simples de email/telefone em logs e respostas publicas (padrao: true)
- `SUPPORT_MAX_RESPONSE_CHARS`: limite duro para respostas do agente de suporte (padrao: 1200)
- `SUPPORT_CATEGORY_TERMS_OVERRIDES` / `SUPPORT_SEVERITY_TERMS_OVERRIDES`: strings no formato `categoria:termo1,termo2;...` para ajustar politicas rapidamente.
## Etapa 8 - Guardrails Globais (normalizacao sem acentos, validacao, anti-injection, PII, moderacao)
- Normalizacao de entrada: GuardrailsService.preprocess_input remove acentos e simbolos definidos em GUARDRAILS_NORMALIZE_STRIP_SYMBOLS, gera preview mascarado e mantem o roteamento consistente entre /chat e /route.
- Validacao forte: validate_payload aplica GUARDRAILS_MAX_INPUT_CHARS, obriga message string nao vazia e valida tipos de user_id/metadata, respondendo 422 com {error:invalid_input} sem stack trace.
- Anti prompt-injection: cleanse_injection elimina instrucoes meta listadas em GUARDRAILS_ANTI_INJECTION_PATTERNS, marca guardrails_injection_detected e descarta chunks suspeitos antes do RAG.
- Mascaramento de PII: mask_text protege logs, meta e respostas seguindo PII_MASK_*; o meta expone apenas guardrails_masked_input_preview sanitizado.
- Moderacao & truncagem: moderate_text honra blocklists (GUARDRAILS_MODERATION_BLOCKLIST_TERMS) conforme o modo (strict|balanced|off) e postprocess_output trunca respostas acima de GUARDRAILS_MAX_OUTPUT_CHARS sinalizando guardrails_output_truncated.
- Telemetria unificada: meta agrega guardrails_pre_ms, guardrails_post_ms, guardrails_total_ms, modo ativo e flags de PII/moderacao; contadores (guardrails_inputs_total, moderation_blocked_total, etc.) ficam acessiveis via GuardrailsService.metrics_snapshot().
- Diagnostico opcional: habilite GUARDRAILS_DIAGNOSTICS_ENABLED=true e use GET /guardrails/diagnostics?query=... para inspecionar texto normalizado (mascarado), termos detectados e snapshot de contadores; desabilitado responde 404.
- Cobertura: pytest --cov=app.guardrails --cov-report=term garante ~93% da camada de guardrails, cobrindo normalizacao, validacao, anti-injection, PII, moderacao e diagnostico.

## Etapa 9 — Redirect & Slack Agent
- Mecanismo human-in-the-loop: RedirectService avalia cada chamada ao `/chat` (exceto rotas `slack`). Se `GUARDRAILS_REDIRECT_ALWAYS=true`, se o roteador reportar `confidence` abaixo de `REDIRECT_CONFIDENCE_THRESHOLD` ou se a mensagem contiver pedido explicito por humano, a resposta e padronizada com `agent="redirect"`, motivo (`redirect_reason`) e `ticket_id` simulado.
- Rota `slack`: o RouterAgent reconhece pedidos diretos como "quero falar com humano" e retorna `route="slack"`. Nesse caso o SlackAgent responde confirmando o encaminhamento para o canal configurado, mantendo o fluxo automatico sem acionar RedirectService.
- SlackAgent mockado: implementado em `app/agents/slack_agent.py`, integra-se a um `HandoffFlow` em memoria e usa `MockSlackClient`. Nenhuma chamada externa e realizada; mensagens sao apenas registradas/logadas.
- Controles por ENV: defina `SLACK_AGENT_ENABLED=false` para desligar o agente simulado ou ajuste `SLACK_CHANNEL_DEFAULT` para representar outro canal. O redirect pode ser desligado com `REDIRECT_ENABLED=false` ou forçado com `GUARDRAILS_REDIRECT_ALWAYS=true`.
- Exemplos `/chat`:
  - Pedido humano direto (`route=slack`):
    ```json
    {
      "agent": "slack",
      "content": "Acionei o time humano no canal support-humans. Eles vao acompanhar e retornar em breve.",
      "meta": {
        "route": "slack",
        "channel": "support-humans",
        "handoff_status": "forwarded",
        "redirected": true
      }
    }
    ```

## Etapa 10 — Observabilidade e Métricas Globais
- Endpoint `/metrics` (habilitado com `METRICS_ENABLED=true`) expõe contadores e histogramas no formato Prometheus. Exemplos:
  ```
  chat_requests_total{agent="knowledge"} 42
  chat_redirect_total 3
  guardrails_accents_stripped_total 5
  chat_request_latency_ms_bucket{le="1000", correlation_id="abc123"} 1
  ```
  Use `curl http://localhost:8000/metrics` e configure o scraper do Prometheus apontando para o mesmo endpoint.
- Endpoint `/readiness` (controlado por `READINESS_ENABLED`) valida dependências críticas:
  - `openai_api_key`: chave presente.
  - `embeddings_store`: índice em `data/rag/index` disponível quando `RAG_ENABLED=true`.
  - `system_resources`: CPU e memória abaixo dos limites (`READINESS_CPU_THRESHOLD`, `READINESS_MEMORY_THRESHOLD_MB`).
  Resposta `200` indica serviço pronto; falhas retornam `503` com detalhes por check.
- Tracing com correlation-id:
  - Cada request a `/chat` aceita `X-Correlation-ID`; se ausente, gera UUID.
  - O ID aparece nos logs, em `meta.correlation_id` da resposta e no cabeçalho de saída.
- Logs estruturados (default `LOG_FORMAT=json`):
  ```json
  {
    "timestamp": "2024-05-10T12:34:56.789000+00:00",
    "level": "info",
    "message": "chat.success",
    "correlation_id": "abc123",
    "route": "knowledge",
    "agent": "knowledge",
    "latency_ms": 85.7,
    "flags": {"accents_stripped": true, "pii_masked": false}
  }
  ```
  Ajuste `LOG_FORMAT=text` para modo legível durante debug.
- Boas práticas:
  - Use o correlation-id em dashboards para rastrear uma conversa ponta a ponta.
  - Combine `/metrics` com alertas de redirect alto ou latência fora do esperado.
  - `/readiness` pode ser integrado ao load balancer/Kubernetes para remover instâncias degradadas.
  - Confianca baixa (`redirect`):
    ```json
    {
      "agent": "redirect",
      "content": "Your request was redirected to a human agent. A support ticket has been created.",
      "meta": {
        "route": "knowledge",
        "redirect_reason": "low_confidence",
        "ticket_id": "HUM-20250101-001",
        "channel": "support-humans",
        "redirected": true
      }
    }
    ```

## Etapa 11 — Interface Web Customizada
- Frontend React + Vite + TypeScript localizado em `frontend/`, estilizado com TailwindCSS e tema exclusivo (azul profundo + dourado).
- O app consome a API existente (`/chat`, `/route`, `/health`, `/readiness`, `/metrics`) respeitando correlation-id e guardrails.
- Componentes principais:
  - **Chat Console**: histórico em forma de bolhas, agente destacado, citações clicáveis, ID de correlação exibido em cada resposta, botões "Novo Chat" e "Copiar" e spinner durante o processamento.
  - **Status Page**: painéis para `/health` e `/readiness` com indicadores visuais de disponibilidade.
  - **Metrics Page**: painel raw que exibe `/metrics` com atualização manual.
- Experiência aprimorada:
  - Histórico persistido em `localStorage` para manter o contexto após recarregar a página.
  - Tratamento elegante de erros, alertas sutis e layout responsivo.
  - Cabeçalho com navegação, logotipo "Agent Workflow" e rodapé institucional.

### Executando o frontend
1. `cd frontend`
2. `npm install`
3. Copie `.env.example` para `.env` e ajuste `VITE_API_BASE_URL` conforme o endpoint do backend (padrao: `http://127.0.0.1:8000`).
4. `npm run dev` → acesse `http://localhost:5173`.

### Build de produção
- `npm run build` gera a pasta `dist/` pronta para deploy em Vercel, Netlify, Render ou ambientes estáticos equivalentes.
- Opcional: `npm run preview` para validar a build localmente.

### Ajustes no backend
- Habilite CORS adicionando a origem do frontend em `FRONTEND_ALLOWED_ORIGINS` (ex.: `http://localhost:5173`).
- Confirme que as variáveis da Etapa 10 permanecem ativas (`METRICS_ENABLED`, `READINESS_ENABLED`, etc.) para que os painéis funcionem.

### Funcionalidades para validação manual
1. "What are the fees of the Maquininha Smart?" → Knowledge Agent com citações visíveis.
2. "I can’t sign in to my account." → Support Agent com meta de ticket.
3. "I want to talk to a human." → Slack Agent ou redirect, destacando o canal humano.
4. "Escreva um discurso de odio." → Guardrails bloqueiam/moderam a saída com alerta na interface.
5. Página **Status** → valida `/health` e `/readiness`.
6. Página **Metrics** → exibe exportação Prometheus completa.

### Variáveis de ambiente relevantes
- Frontend: `VITE_API_BASE_URL` (arquivo `frontend/.env`).
- Backend: `FRONTEND_ALLOWED_ORIGINS` controla as origens liberadas para o navegador.

### Capturas de tela
- Recomenda-se registrar uma captura do console de chat em operação para documentação interna ou README públicos.
