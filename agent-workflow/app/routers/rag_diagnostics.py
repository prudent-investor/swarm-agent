from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.rag import (
    QueryCache,
    RAGRetriever,
    build_citations,
    build_context,
    filter_chunks,
    HeuristicReranker,
)
from app.agents.knowledge_agent_v2 import FALLBACK_URLS
from app.settings import settings

router = APIRouter()

_retriever = RAGRetriever()
_reranker = HeuristicReranker()
_cache = QueryCache(ttl_seconds=settings.rag_cache_ttl_seconds)


class DiagnosticsRequest(BaseModel):
    query: str = Field(..., min_length=1)


@router.post("/rag/diagnostics")
def diagnostics(payload: DiagnosticsRequest) -> Dict[str, Any]:
    query = payload.query
    retrieved = _retriever.retrieve(query, top_k=settings.rag_top_k * 2)
    reranked = _reranker.rerank(query, retrieved)
    filtered = filter_chunks(reranked)
    context_text, selected = build_context(filtered, max_chars=settings.rag_max_context_chars)
    citations = build_citations(selected, fallback_urls=FALLBACK_URLS)
    return {
        "query": query,
        "retrieved": [chunk.__dict__ for chunk in retrieved],
        "reranked": [chunk.__dict__ for chunk in reranked],
        "filtered_count": len(selected),
        "context_preview": context_text[:500],
        "citations": citations,
    }
