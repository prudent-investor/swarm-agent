from __future__ import annotations

import re
from typing import Iterable, List

from app.services.rag.retriever import RetrievedChunk

INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ignore (all )?previous instructions",
        r"disregard the earlier context",
        r"act as (system|administrator)",
        r"reset the conversation",
    ]
]


def filter_chunks(chunks: Iterable[RetrievedChunk]) -> List[RetrievedChunk]:
    filtered: List[RetrievedChunk] = []
    for chunk in chunks:
        if any(pattern.search(chunk.text) for pattern in INJECTION_PATTERNS):
            continue
        if _looks_like_navigation(chunk.text):
            continue
        filtered.append(chunk)
    return filtered


def _looks_like_navigation(text: str) -> bool:
    lowered = text.lower()
    if len(lowered.split()) <= 3:
        return True
    return any(keyword in lowered for keyword in ["menu", "cookies", "copyright", "termos de uso"])
