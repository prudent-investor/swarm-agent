from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    id: str
    url: str
    title: str | None
    order: int
    text: str
    raw_score: float
    content_hash: str
    ingest_timestamp: str | None
    rank_score: float | None = None


class RAGRetriever:
    def __init__(self, *, index_dir: Path | None = None) -> None:
        self.index_dir = index_dir or (Path("data") / "rag" / "index")
        self._index_cache: List[dict] | None = None

    def retrieve(self, query: str, *, top_k: int | None = None) -> List[RetrievedChunk]:
        query_norm = _normalise_query(query)
        index_entries = self._load_index()
        if not index_entries:
            logger.warning("rag.retriever.index_empty")
            return []

        tokens = [token for token in query_norm.split() if len(token) > 1]
        if not tokens:
            return []

        scored: List[RetrievedChunk] = []
        for entry in index_entries:
            text = entry.get("text", "")
            title = entry.get("title")
            url = _canonical_url(entry.get("url", ""))
            base_score = _score_text(tokens, text)
            title_score = _score_title(tokens, title)
            total_score = base_score + title_score
            if total_score <= 0:
                continue
            scored.append(
                RetrievedChunk(
                    id=entry.get("id", ""),
                    url=url,
                    title=title,
                    order=entry.get("order", 0),
                    text=text,
                    raw_score=total_score,
                    content_hash=entry.get("content_hash", ""),
                    ingest_timestamp=entry.get("captured_at"),
                )
            )

        scored.sort(key=lambda item: item.raw_score, reverse=True)
        limit = top_k or settings.rag_top_k
        min_score = settings.rag_min_score
        results = [item for item in scored[:limit] if item.raw_score >= min_score]
        logger.info(
            "rag.retriever.results",
            extra={"query": query_norm, "count": len(results), "top_score": results[0].raw_score if results else 0.0},
        )
        return results

    def _load_index(self) -> List[dict]:
        if self._index_cache is not None:
            return self._index_cache

        if not self.index_dir.exists():
            logger.warning("rag.retriever.missing_index_dir", extra={"path": str(self.index_dir)})
            self._index_cache = []
            return self._index_cache

        index_files = sorted(self.index_dir.glob("index_*.jsonl"), reverse=True)
        entries: List[dict] = []
        for file in index_files:
            try:
                with file.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        payload.setdefault("url", "")
                        payload.setdefault("title", None)
                        entries.append(payload)
            except OSError as exc:  # pragma: no cover
                logger.error("rag.retriever.read_error", extra={"file": str(file), "error": str(exc)})
                continue

        self._index_cache = entries
        return self._index_cache


def _normalise_query(query: str) -> str:
    query = query.lower().strip()
    query = re.sub(r"\s+", " ", query)
    return query


def _score_text(tokens: Iterable[str], text: str) -> float:
    lowered = text.lower()
    score = 0.0
    for token in tokens:
        occurrences = lowered.count(token)
        if occurrences:
            score += occurrences
    if not score:
        return 0.0
    length_penalty = 1.0 / math.log(len(lowered) + 10, 10)
    return score * length_penalty


def _score_title(tokens: Iterable[str], title: str | None) -> float:
    if not title:
        return 0.0
    lowered = title.lower()
    score = 0.0
    for token in tokens:
        if token in lowered:
            score += settings.rag_rerank_title_boost
    return score


def _canonical_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    if url.endswith("/") and len(url) > len("https://") + 1:
        url = url.rstrip("/")
    return url
