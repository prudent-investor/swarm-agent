from __future__ import annotations

import logging
from typing import Iterable, List

from app.settings import settings

from .retriever import RetrievedChunk

logger = logging.getLogger(__name__)


class HeuristicReranker:
    def __init__(
        self,
        title_boost: float = settings.rag_rerank_title_boost,
        exact_term_boost: float = settings.rag_rerank_exact_term_boost,
        length_penalty: float = settings.rag_rerank_length_penalty,
    ) -> None:
        self.title_boost = title_boost
        self.exact_term_boost = exact_term_boost
        self.length_penalty = length_penalty

    def rerank(self, query: str, chunks: Iterable[RetrievedChunk]) -> List[RetrievedChunk]:
        tokens = [token for token in query.lower().split() if len(token) > 1]
        if not tokens:
            return list(chunks)

        reranked: List[RetrievedChunk] = []
        for chunk in chunks:
            score = chunk.raw_score
            if chunk.title:
                lowered_title = chunk.title.lower()
                for token in tokens:
                    if token in lowered_title:
                        score += self.title_boost
            lowered_text = chunk.text.lower()
            for token in tokens:
                if f" {token} " in lowered_text:
                    score += self.exact_term_boost
            length_factor = max(len(chunk.text), 1)
            penalty = self.length_penalty * (abs(len(chunk.text) - 800) / 800)
            score -= penalty
            chunk.rank_score = score
            reranked.append(chunk)

        reranked.sort(key=lambda item: item.rank_score or 0.0, reverse=True)
        logger.info(
            "rag.reranker.results",
            extra={
                "query": query,
                "top_score": reranked[0].rank_score if reranked else 0,
            },
        )
        return reranked
