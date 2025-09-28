# REPORT

## Checklist do desafio
- [OK] Router integra Knowledge, Support, Custom e Slack/Handoff com normalização de texto.
- [OK] KnowledgeAgent v2 usa RAG com fontes InfinitePay, gera citações e ativa web search opcional.
- [OK] SupportAgent v2 combina FAQ, TicketTool, UserProfileTool e AccountStatusTool com masking de PII.
- [OK] Slack/Handoff Agent confirma escalonamento, preserva metadados e respeita modos mock/real.
- [OK] Guardrails globais com remoção de acentos, anti-injection, moderação, truncagem e métricas.
- [OK] Observabilidade completa (/metrics, logs JSON, correlation-id, /readiness com limites configuráveis).
- [OK] Containerização para backend (Render) e frontend (Vercel), com CORS e health checks.
- [OK] Seeds/whitelist RAG atualizados com todas as páginas InfinitePay exigidas.
- [OK] Web search configurável via variáveis de ambiente.
- [OK] Coleção Postman e script de smoke automatizado cobrindo endpoints críticos.

## Testes executados
- `pytest -q` (passou – 113 testes). Consulte `agent-workflow` para reproduzir.
- `./smoke-tests.sh` (não executado neste ambiente – requer API em execução com credenciais OpenAI válidas).

## Pendências e plano
- Nenhuma pendência funcional. Para validar em staging/produção, executar `./smoke-tests.sh` apontando para o backend publicado e revisar o retorno do Slack real.

## Deploy
- **Render (backend)**: construir imagem com `Dockerfile.backend`, expor porta 8000, definir variáveis do `.env.example`, configurar health em `/health` e readiness em `/readiness`.
- **Vercel (frontend)**: usar build `npm run build`, apontar `VITE_API_BASE_URL` para o domínio Render, habilitar headers de CORS já contemplados em `FRONTEND_ALLOWED_ORIGINS`.
- Após deploy, rodar `./smoke-tests.sh` (com `BASE_URL` público) e importar `collections/agent-workflow.postman_collection.json` para uma verificação manual.
