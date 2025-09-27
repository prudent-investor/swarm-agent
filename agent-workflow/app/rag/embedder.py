from __future__ import annotations

import logging
from typing import Iterable, List

from openai import OpenAI

from app.settings import settings

from .splitter import Chunk

logger = logging.getLogger(__name__)


class ChunkEmbedder:
    def __init__(self, *, model: str, client: OpenAI | None = None, min_length: int = 30) -> None:
        api_key = settings.openai_api_key
        self.model = model
        self.client = client or OpenAI(api_key=api_key)
        self.min_length = min_length

    def embed(self, chunks: Iterable[Chunk]) -> List[Chunk]:
        chunk_list = list(chunks)
        texts = [chunk.text for chunk in chunk_list if len(chunk.text) >= self.min_length]
        if not texts:
            logger.info("rag.embedder.skip", extra={"reason": "no_chunks"})
            return chunk_list

        try:
            response = self.client.embeddings.create(model=self.model, input=texts)
        except Exception as exc:  # pragma: no cover
            logger.error("rag.embedder.error", extra={"error": str(exc)})
            return chunk_list

        embeddings = iter(response.data)
        for chunk in chunk_list:
            if len(chunk.text) < self.min_length:
                continue
            try:
                embedding = next(embeddings)
            except StopIteration:  # pragma: no cover
                break
            chunk.embedding = embedding.embedding

        logger.info("rag.embedder.completed", extra={"embedded": sum(1 for c in chunk_list if c.embedding)})
        return chunk_list
