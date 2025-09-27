from __future__ import annotations

from typing import Iterable, List, Tuple

from .retriever import RetrievedChunk


def build_context(
    chunks: Iterable[RetrievedChunk],
    *,
    max_chars: int,
) -> Tuple[str, List[RetrievedChunk]]:
    selected: List[RetrievedChunk] = []
    used_urls: set[str] = set()
    context_parts: List[str] = []
    total_chars = 0

    for chunk in chunks:
        if chunk.url in used_urls:
            continue
        snippet = chunk.text.strip()
        if not snippet:
            continue
        snippet_with_meta = f"URL: {chunk.url}\nTrecho: {snippet}"
        if total_chars + len(snippet_with_meta) > max_chars:
            break
        context_parts.append(snippet_with_meta)
        selected.append(chunk)
        used_urls.add(chunk.url)
        total_chars += len(snippet_with_meta)

    context = "\n\n".join(context_parts)
    return context, selected
