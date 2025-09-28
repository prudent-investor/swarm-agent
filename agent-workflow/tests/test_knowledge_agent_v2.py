from __future__ import annotations

from typing import List

import pytest

from app.agents.base import AgentRequest
from app.agents.knowledge_agent_v2 import KnowledgeAgent
from app.services.llm_provider import LLMProviderError
from app.services.rag import QueryCache, RetrievedChunk
from app.services.web_search import WebSearchResult
from app.settings import settings


class StubRetriever:
    def __init__(self, results: List[RetrievedChunk]):
        self._results = results

    def retrieve(self, query: str, *, top_k: int | None = None):
        return list(self._results)


class StubReranker:
    def rerank(self, query: str, chunks):
        for chunk in chunks:
            chunk.rank_score = (chunk.rank_score or 0) + 1
        return list(chunks)


class StubProvider:
    def __init__(self, text: str, should_fail: bool = False):
        self.text = text
        self.should_fail = should_fail

    def generate_response(self, **_: object) -> str:
        if self.should_fail:
            raise LLMProviderError("fail")
        return self.text


class StubWebSearch:
    def __init__(self, results=None):
        self._results = results or []

    def search(self, query: str, *, top_k: int = 3):
        return list(self._results)


@pytest.fixture
def sample_chunks() -> List[RetrievedChunk]:
    return [
        RetrievedChunk(
            id="chunk-1",
            url="https://www.infinitepay.io/maquininha",
            title="Maquininha",
            order=0,
            text="A maquininha InfinitePay possui taxas competitivas.",
            raw_score=0.9,
            content_hash="c1",
            ingest_timestamp=None,
            rank_score=0.9,
        )
    ]


def test_knowledge_agent_returns_citations(sample_chunks):
    agent = KnowledgeAgent(
        provider=StubProvider("Resposta fundamentada."),
        retriever=StubRetriever(sample_chunks),
        reranker=StubReranker(),
        cache=QueryCache(ttl_seconds=300),
        web_search=StubWebSearch(),
    )

    response = agent.run(AgentRequest(message="Como funciona a maquininha?"))

    assert response.agent == "knowledge"
    assert response.citations and response.citations[0]["url"].endswith("/maquininha")
    assert response.meta["rag_used"] is True
    assert response.meta["fallback_used"] is False


def test_knowledge_agent_fallback_when_no_results():
    agent = KnowledgeAgent(
        provider=StubProvider("fallback"),
        retriever=StubRetriever([]),
        reranker=StubReranker(),
        cache=QueryCache(ttl_seconds=300),
        web_search=StubWebSearch(),
    )

    response = agent.run(AgentRequest(message="Pergunta desconhecida"))

    assert response.meta["fallback_used"] is True
    assert response.citations
    assert any("infinitepay.io" in citation["url"] for citation in response.citations)


def test_knowledge_agent_handles_greetings_and_tracks_history():
    cache = QueryCache(ttl_seconds=300)
    agent = KnowledgeAgent(
        provider=StubProvider("fallback"),
        retriever=StubRetriever([]),
        reranker=StubReranker(),
        cache=cache,
        web_search=StubWebSearch(),
    )

    first = agent.run(AgentRequest(message="Olá", user_id="client789"))
    assert first.meta["fallback_used"] is True
    assert first.meta["previous_message_remembered"] is False
    assert "Como posso ajudar" in first.content

    second = agent.run(AgentRequest(message="Ainda preciso de suporte", user_id="client789"))
    assert second.meta["fallback_used"] is True
    assert second.meta["previous_message_remembered"] is True
    assert "ainda não encontrei" in second.content.lower()


def test_knowledge_agent_switches_language_based_on_query():
    cache = QueryCache(ttl_seconds=300)
    agent = KnowledgeAgent(
        provider=StubProvider("fallback"),
        retriever=StubRetriever([]),
        reranker=StubReranker(),
        cache=cache,
        web_search=StubWebSearch(),
    )

    portuguese = agent.run(AgentRequest(message="Oi", user_id="lang-pt"))
    assert "Olá" in portuguese.content
    assert portuguese.meta["response_language"] == "pt"

    english = agent.run(AgentRequest(message="Hello", user_id="lang-en"))
    assert "Hello" in english.content
    assert english.meta["response_language"] == "en"


def test_knowledge_agent_remembers_user_name():
    cache = QueryCache(ttl_seconds=300)
    agent = KnowledgeAgent(
        provider=StubProvider("fallback"),
        retriever=StubRetriever([]),
        reranker=StubReranker(),
        cache=cache,
        web_search=StubWebSearch(),
    )

    first = agent.run(AgentRequest(message="Meu nome é Jefferson", user_id="client-name"))
    assert "Jefferson" in first.content
    assert first.meta["remembered_name"] is True

    second = agent.run(AgentRequest(message="Lembra do meu nome ?", user_id="client-name"))
    assert "Jefferson" in second.content
    assert second.meta["remembered_name"] is True
    assert second.meta["response_language"] == "pt"


def test_knowledge_agent_cache_hit(sample_chunks):
    cache = QueryCache(ttl_seconds=300)
    agent = KnowledgeAgent(
        provider=StubProvider("Resposta."),
        retriever=StubRetriever(sample_chunks),
        reranker=StubReranker(),
        cache=cache,
        web_search=StubWebSearch(),
    )

    first = agent.run(AgentRequest(message="Qual a taxa da maquininha?"))
    second = agent.run(AgentRequest(message="Qual a taxa da maquininha?"))

    assert first.meta["cache_hit"] is False
    assert second.meta["cache_hit"] is True


def test_knowledge_agent_uses_web_search(monkeypatch):
    monkeypatch.setattr(settings, "web_search_enabled", True)
    web_results = [WebSearchResult(title="Artigo Externo", url="https://example.com/artigo", snippet="Resumo externo.")]
    agent = KnowledgeAgent(
        provider=StubProvider("Resposta externa."),
        retriever=StubRetriever([]),
        reranker=StubReranker(),
        cache=QueryCache(ttl_seconds=300),
        web_search=StubWebSearch(web_results),
    )

    response = agent.run(AgentRequest(message="Qual e o cartao InfinitePay?"))

    assert response.meta["web_search_used"] is True
    assert any(citation["source_type"] == "external" for citation in response.citations)
