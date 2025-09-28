# REPORT

## Checklist do desafio
- [OK] RouterAgent orquestra Knowledge, Support, Custom e Slack/Handoff (incluindo heurísticas offline e normalização de texto).
- [OK] KnowledgeAgent v2 usa RAG das páginas InfinitePay exigidas, retorna citações obrigatórias e aciona web search externa quando habilitada.
- [OK] SupportAgent v2 opera FAQ, TicketTool, UserProfileTool e AccountStatusTool com masking de PII e políticas de escalonamento.
- [OK] Slack/Handoff Agent confirma a intenção do usuário, registra token de confirmação, preserva ticket/categoria/prioridade e trata modos mock/real, falha e desligado.
- [OK] Guardrails globais: remoção de acentos, anti-injection, moderação, masking, truncagem e métricas dedicadas.
- [OK] Observabilidade: logs JSON com correlation-id, /metrics com séries por agente/guardrail/handoff, /readiness com thresholds configuráveis.
- [OK] Containerização e deploy: Dockerfiles separados, CORS configurável (`FRONTEND_ALLOWED_ORIGINS`), docker-compose e instruções Render/Vercel.
- [OK] Seeds/whitelist RAG atualizados com todas as URLs InfinitePay listadas no enunciado.
- [OK] Web search configurável (`WEB_SEARCH_*`) e marcada como fonte externa nas citações.
- [OK] Coleção Postman (`collections/agent-workflow.postman_collection.json`) e script `smoke-tests.sh` cobrindo health, router, 4 agentes, tickets, metrics e readiness.

## Testes executados
- `python -m pytest -q`
- `python -m pytest --cov=app --cov-report=term` → cobertura global 86%
- `./smoke-tests.sh` (BASE_URL local com Uvicorn dedicado)

## Pendências e plano
- Não há pendências funcionais. Para novos ambientes, repetir os smokes apontando para o host público e validar o fluxo Slack real (caso habilitado).

## Deploy
- **Render (backend)**: construir com `Dockerfile.backend`, expor porta 8000, definir variáveis do `.env.example`, e configurar probes em `/health` e `/readiness`.
- **Vercel (frontend)**: usar preset Vite/Other com `npm run build`, configurar `VITE_API_BASE_URL` para o backend público e manter CORS alinhado (`FRONTEND_ALLOWED_ORIGINS`).
- Após o deploy, rodar `./smoke-tests.sh` com `BASE_URL` apontado para produção e, opcionalmente, importar a coleção Postman para verificação manual.
