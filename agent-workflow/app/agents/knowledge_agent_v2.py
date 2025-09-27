from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import Iterable, List, Optional

from app.agents.base import Agent, AgentControlledError, AgentRequest, AgentResponse
from app.services.llm_provider import LLMProvider, LLMProviderError
from app.services.rag import (
    Citation,
    HeuristicReranker,
    QueryCache,
    RAGRetriever,
    RetrievedChunk,
    build_citations,
    build_context,
    filter_chunks,
)
from app.services.web_search import NoopWebSearchClient, WebSearchClient, WebSearchResult
from app.guardrails import get_guardrails_service
from app.settings import settings

logger = logging.getLogger(__name__)
_guardrails_service = get_guardrails_service()

FALLBACK_URLS = ["https://www.infinitepay.io"]


class KnowledgeAgent(Agent):
    name = "knowledge"

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        retriever: Optional[RAGRetriever] = None,
        reranker: Optional[HeuristicReranker] = None,
        cache: Optional[QueryCache] = None,
        web_search: Optional[WebSearchClient] = None,
    ) -> None:
        self._provider = provider or LLMProvider()
        self._retriever = retriever or RAGRetriever()
        self._reranker = reranker or HeuristicReranker()
        self._cache = cache or QueryCache(ttl_seconds=settings.rag_cache_ttl_seconds)
        self._web_search = web_search or NoopWebSearchClient()

    def run(self, payload: AgentRequest) -> AgentResponse:
        start_time = time.perf_counter()
        query = payload.message.strip()
        normalised = query.lower()

        if not settings.rag_enabled:
            return self._fallback_response(query, cache_hit=False, rag_used=False, web_search_used=False)

        cache_key = normalised
        cached = self._cache.get(cache_key)
        cache_hit = cached is not None
        if cached:
            context_text, selected_chunks = cached["context"], _deserialize_chunks(cached["chunks"])
            reranked_chunks = selected_chunks
        else:
            retrieved = self._retriever.retrieve(query, top_k=settings.rag_top_k)
            reranked = self._reranker.rerank(query, retrieved)
            filtered = filter_chunks(reranked)
            filtered = _guardrails_service.filter_context(filtered)
            context_text, selected_chunks = build_context(filtered, max_chars=settings.rag_max_context_chars)
            reranked_chunks = selected_chunks
            serialisable = {
                "context": context_text,
                "chunks": [_serialise_chunk(chunk) for chunk in selected_chunks],
            }
            self._cache.set(cache_key, serialisable)

        rag_used = bool(context_text)
        fallback_used = not rag_used
        web_search_used = False
        external_citations: List[WebSearchResult] = []

        if not rag_used and settings.web_search_enabled:
            external_citations = self._web_search.search(query, top_k=3)
            web_search_used = bool(external_citations)

        if not rag_used and not external_citations:
            response = self._fallback_response(query, cache_hit=cache_hit, rag_used=False, web_search_used=False)
            response.meta.update({"duration_ms": round((time.perf_counter() - start_time) * 1000, 2)})
            return response

        try:
            context_snippets = []
            if context_text:
                context_snippets.append(context_text)
            if external_citations:
                for result in external_citations:
                    snippet = f"Fonte externa: {result.url}\nTrecho: {result.snippet}"
                    context_snippets.append(snippet)

            composed_context = "\n\n".join(context_snippets)
            system_prompt = (
                "Voce e o KnowledgeAgent v2 da InfinitePay. Use apenas o contexto fornecido para responder"
                " em portugues do Brasil, de forma concisa (2 a 5 frases) e sempre cite as fontes."
                " Caso o contexto nao cubra a pergunta, informe isso de maneira honesta."
            )
            user_prompt = (
                f"Pergunta do usuario: {query}\n\n"
                f"Contexto de suporte:\n{composed_context}\n\n"
                "Instrucao: gere uma resposta curta, objetiva e cite explicitamente as fontes relevantes"
                " usando os titulos das paginas oferecidas."
            )
            ai_response = self._provider.generate_response(
                system_prompt=system_prompt,
                user_message=user_prompt,
                metadata={"rag_used": rag_used, "web_search_used": web_search_used},
                temperature=0.2,
            )
        except LLMProviderError as exc:
            logger.error("rag.knowledge.llm_failure", extra={"error": str(exc)})
            raise AgentControlledError(
                error="knowledge_agent_unavailable",
                status_code=503,
                details="Nao foi possivel contatar o modelo de linguagem.",
                agent=self.name,
            ) from exc

        citations = build_citations(
            reranked_chunks if rag_used else [],
            fallback_urls=FALLBACK_URLS,
            external_sources=[
                _external_citation(result) for result in external_citations
            ] if external_citations else None,
        )

        meta = {
            "rag_used": rag_used,
            "top_k_selected": len(reranked_chunks),
            "avg_score": _average_score(reranked_chunks),
            "cache_hit": cache_hit,
            "fallback_used": fallback_used,
            "web_search_used": web_search_used,
            "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
        }

        return AgentResponse(
            agent=self.name,
            content=_normalise_text(ai_response),
            citations=citations,
            meta=meta,
        )

    def _fallback_response(self, query: str, *, cache_hit: bool, rag_used: bool, web_search_used: bool) -> AgentResponse:
        content = (
            "Nao encontrei informacoes suficientes no acervo atual da InfinitePay para responder com precisao."
            " Recomendo consultar a pagina oficial ou documentacao atualizada."
        )
        citations = build_citations([], fallback_urls=FALLBACK_URLS)
        meta = {
            "rag_used": rag_used,
            "top_k_selected": 0,
            "avg_score": 0.0,
            "cache_hit": cache_hit,
            "fallback_used": True,
            "web_search_used": web_search_used,
            "duration_ms": 0.0,
        }
        return AgentResponse(agent=self.name, content=content, citations=citations, meta=meta)


def _external_citation(result: WebSearchResult) -> Citation:
    return Citation(title=result.title or _title_from_external(result.url), url=result.url, source_type="external")


def _title_from_external(url: str) -> str:
    if not url:
        return "Fonte Externa"
    parts = url.split("//", 1)[-1]
    return parts.split("/", 1)[0]


def _average_score(chunks: Iterable[RetrievedChunk]) -> float:
    scores = [chunk.rank_score or chunk.raw_score for chunk in chunks if chunk.rank_score or chunk.raw_score]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 3)


def _normalise_text(text: str) -> str:
    return " ".join(text.strip().split())


def _serialise_chunk(chunk: RetrievedChunk) -> dict:
    return {
        "id": chunk.id,
        "url": chunk.url,
        "title": chunk.title,
        "order": chunk.order,
        "text": chunk.text,
        "raw_score": chunk.raw_score,
        "content_hash": chunk.content_hash,
        "ingest_timestamp": chunk.ingest_timestamp,
        "rank_score": chunk.rank_score,
    }


def _deserialize_chunks(serialised: List[dict]) -> List[RetrievedChunk]:
    chunks: List[RetrievedChunk] = []
    for entry in serialised:
        chunks.append(
            RetrievedChunk(
                id=entry.get("id", ""),
                url=entry.get("url", ""),
                title=entry.get("title"),
                order=entry.get("order", 0),
                text=entry.get("text", ""),
                raw_score=entry.get("raw_score", 0.0),
                content_hash=entry.get("content_hash", ""),
                ingest_timestamp=entry.get("ingest_timestamp"),
                rank_score=entry.get("rank_score"),
            )
        )
    return chunks



