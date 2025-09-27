from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .cleaner import CleanDocument


dataclass
class Chunk:
    id: str
    url: str
    title: str | None
    order: int
    text: str
    content_hash: str
    embedding: List[float] | None = None


def split_document(
    document: CleanDocument,
    *,
    chunk_size: int,
    overlap: int,
) -> List[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = document.text
    if not text:
        return []

    chunks: List[Chunk] = []
    step = max(1, chunk_size - overlap)
    start = 0
    order = 0

    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunk_id = f"{document.content_hash}-{order}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    url=document.url,
                    title=document.title,
                    order=order,
                    text=chunk_text,
                    content_hash=document.content_hash,
                )
            )
            order += 1
        start += step

    return chunks
