from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str


class WebSearchClient(Protocol):
    def search(self, query: str, *, top_k: int = 3) -> List[WebSearchResult]:
        ...


class NoopWebSearchClient:
    def search(self, query: str, *, top_k: int = 3) -> List[WebSearchResult]:
        return []
