import re
from typing import Iterable, List

import pytest
from fastapi.testclient import TestClient

from app.agents.base import Route, RoutingDecision
from app.agents.custom_agent import CustomAgent
from app.agents.knowledge_agent_v2 import KnowledgeAgent
from app.agents.support_agent_v2 import CustomerSupportAgent
from app.main import app
from app.routers import chat as chat_router
from app.guardrails.service import PostprocessResult, PreprocessResult
from app.services.llm_provider import LLMProvider
from app.services.rag import HeuristicReranker, QueryCache, RAGRetriever
from app.services.web_search import WebSearchResult
from app.settings import settings


class ScenarioRouter:
    def route_message(self, message: str) -> RoutingDecision:
        lowered = message.lower()
        if "transfer" in lowered:
            return RoutingDecision(route=Route.support, hint="support_transfers", confidence=0.9)
        if any(term in lowered for term in ["sign in", "log in", "login"]):
            return RoutingDecision(route=Route.support, hint="support_access", confidence=0.9)
        return RoutingDecision(route=Route.knowledge, hint="knowledge_product", confidence=0.95)


class ScriptedLLMProvider(LLMProvider):
    def __init__(self) -> None:
        pass

    def generate_response(self, *, system_prompt: str, user_message: str, metadata=None, temperature: float = 0.2) -> str:  # type: ignore[override]
        latest = _extract_latest_message(user_message)
        context = _extract_context(user_message)
        latest_lower = latest.lower()
        external_sources = _extract_external_sources(context)

        if "maquininha smart" in latest_lower and "fee" in latest_lower:
            return (
                "InfinitePay communicates that the Maquininha Smart starts at 0,75% on debit, 2,69% on one-time credit and around "
                "8,99% for 12 instalments, while Pix keeps a 0% rate."
            )
        if "maquininha smart" in latest_lower and "cost" in latest_lower:
            return (
                "The Maquininha Smart is sold for 12 instalments of R$ 16,58 for the first device, with no rental or penalty fees."
            )
        if "rates" in latest_lower and "debit" in latest_lower:
            return (
                "InfinitePay lists debit transactions from 0,75%, one-time credit from 2,69% and credit in 12x from 8,99%, keeping Pix at zero."
            )
        if "phone" in latest_lower and "card machine" in latest_lower:
            return (
                "You can turn your phone into a card machine with InfiniteTap on Android or Tap to Pay on iPhone: open the app, choose "
                "the InfiniteTap/Tap to Pay option, enter the amount and let the customer tap the card. The same Maquininha Smart "
                "rates apply to these mobile payments."
            )
        if "pix parcelado" in latest_lower:
            return (
                "Pix Parcelado lets shoppers pay the first instalment within up to 30 days and split the remaining balance according "
                "to the schedule chosen in the app, keeping everything managed directly in InfinitePay."
            )
        if "palmeiras" in latest_lower and external_sources:
            url, snippet = external_sources[0]
            return f"Latest match update: {snippet} Fonte: {url}."
        if any(term in latest_lower for term in ["notícias", "noticias", "news"]):
            if external_sources:
                details = "; ".join(f"{snippet} ({url})" for url, snippet in external_sources)
                return f"Atualidades de São Paulo: {details}."

        if context:
            return "Here is a summary based on the available context."
        return "I could not find supporting information in the provided context."


class StubWebSearch:
    def search(self, query: str, *, top_k: int = 3) -> List[WebSearchResult]:
        lowered = query.lower()
        if "palmeiras" in lowered:
            return [
                WebSearchResult(
                    title="Palmeiras vence fora de casa",
                    url="https://sports.example.com/palmeiras-santos",
                    snippet="Palmeiras venceu o Santos por 2 a 1 em 30 de setembro de 2025 no Allianz Parque",
                )
            ]
        if "sao paulo" in lowered or "são paulo" in lowered:
            return [
                WebSearchResult(
                    title="Expansão do metrô paulistano",
                    url="https://news.example.com/sp-metro",
                    snippet="São Paulo anunciou novas obras de metrô em 1º de outubro de 2025",
                ),
                WebSearchResult(
                    title="Virada Cultural 2025",
                    url="https://news.example.com/sp-virada",
                    snippet="A prefeitura confirmou a Virada Cultural com programação para 5 de outubro de 2025",
                ),
            ]
        return []


class EchoLLMProvider(LLMProvider):
    def __init__(self, text: str = "Mensagem genérica.") -> None:
        self._text = text

    def generate_response(self, *, system_prompt: str, user_message: str, metadata=None, temperature: float = 0.2) -> str:  # type: ignore[override]
        return self._text


class SelectiveRetriever(RAGRetriever):
    def retrieve(self, query: str, *, top_k: int | None = None):  # type: ignore[override]
        lowered = query.lower()
        off_domain_terms = ["palmeiras", "sao paulo", "são paulo", "noticias", "notícias"]
        if any(term in lowered for term in off_domain_terms):
            return []
        return super().retrieve(query, top_k=top_k)


class RelaxedGuardrails:
    def preprocess_input(self, *, message: str, user_id, metadata, origin: str) -> PreprocessResult:  # type: ignore[override]
        return PreprocessResult(
            message=message.strip(),
            masked_for_log=message.strip(),
            flags={
                "accents_stripped": False,
                "injection_detected": False,
                "pii_masked": False,
            },
            detected_injections=[],
            violations=[],
            latency_ms=0.0,
        )

    def postprocess_output(self, content: str) -> PostprocessResult:  # type: ignore[override]
        return PostprocessResult(
            content=content,
            flags={
                "moderation_blocked": False,
                "output_truncated": False,
                "pii_masked_response": False,
            },
            latency_ms=0.0,
        )

    def filter_context(self, chunks):  # type: ignore[override]
        return list(chunks)


def _extract_latest_message(prompt: str) -> str:
    match = re.search(r"Latest user message:\s*(.+)", prompt)
    return match.group(1).strip() if match else ""


def _extract_context(prompt: str) -> str:
    if "Support context:" not in prompt:
        return ""
    segment = prompt.split("Support context:\n", 1)[-1]
    for delimiter in ["\n\nInstruction:", "\nInstruction:"]:
        if delimiter in segment:
            segment = segment.split(delimiter, 1)[0]
            break
    return segment.strip()


def _extract_external_sources(context: str) -> List[tuple[str, str]]:
    results: List[tuple[str, str]] = []
    lines = context.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("External source:"):
            url = line.split("External source:", 1)[1].strip()
            snippet = ""
            if index + 1 < len(lines) and lines[index + 1].startswith("Excerpt:"):
                snippet = lines[index + 1].split("Excerpt:", 1)[1].strip()
            results.append((url, snippet))
    return results


@pytest.fixture
def chat_client(monkeypatch) -> Iterable[TestClient]:
    monkeypatch.setattr(settings, "web_search_enabled", True)
    monkeypatch.setattr(settings, "web_search_provider", "stub")
    monkeypatch.setattr(settings, "guardrails_enabled", False)
    monkeypatch.setattr(chat_router, "_guardrails_service", RelaxedGuardrails())

    router = ScenarioRouter()
    app.dependency_overrides[chat_router.get_router_agent] = lambda: router

    slack_agent = chat_router._slack_agent

    def _agents_override():
        knowledge_agent = KnowledgeAgent(
            provider=ScriptedLLMProvider(),
            retriever=SelectiveRetriever(),
            reranker=HeuristicReranker(),
            cache=QueryCache(ttl_seconds=120),
            web_search=StubWebSearch(),
        )
        support_agent = CustomerSupportAgent()
        custom_agent = CustomAgent(provider=EchoLLMProvider())
        return {
            Route.knowledge: knowledge_agent,
            Route.support: support_agent,
            Route.custom: custom_agent,
            Route.slack: slack_agent,
        }

    app.dependency_overrides[chat_router.get_agents] = _agents_override

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(chat_router.get_router_agent, None)
    app.dependency_overrides.pop(chat_router.get_agents, None)


@pytest.mark.parametrize(
    "message,expected_snippets,expected_url_fragment",
    [
        (
            "What are the fees of the Maquininha Smart",
            ["0,75%", "2,69%", "8,99%"],
            "infinitepay.io",
        ),
        (
            "What is the cost of the Maquininha Smart?",
            ["12 instalments", "R$ 16,58"],
            "infinitepay.io/maquininha",
        ),
        (
            "What are the rates for debit and credit card transactions?",
            ["0,75%", "2,69%"],
            "infinitepay.io",
        ),
        (
            "How can I use my phone as a card machine?",
            ["InfiniteTap", "Tap to Pay", "same maquininha smart rates"],
            "infinitepay.io/tap-to-pay",
        ),
        (
            "How does Pix Parcelado work?",
            ["30 days", "split the remaining balance"],
            "infinitepay.io/pix-parcelado",
        ),
    ],
)
def test_knowledge_answers_use_rag(chat_client: TestClient, message: str, expected_snippets: List[str], expected_url_fragment: str) -> None:
    response = chat_client.post("/chat", json={"message": message, "user_id": "client-knowledge"})
    assert response.status_code == 200
    body = response.json()

    assert body["agent"] == "knowledge"
    assert body["meta"]["rag_used"] is True
    assert body["meta"].get("web_search_used") is False

    content_lower = body["content"].lower()
    for snippet in expected_snippets:
        assert snippet.lower() in content_lower

    assert any(expected_url_fragment in citation["url"] for citation in body["citations"])


def test_web_search_for_palmeiras(chat_client: TestClient) -> None:
    response = chat_client.post("/chat", json={"message": "Quando foi o último jogo do Palmeiras?", "user_id": "client-sports"})
    assert response.status_code == 200
    body = response.json()

    assert body["agent"] == "knowledge"
    assert body["meta"]["rag_used"] is False
    assert body["meta"]["web_search_used"] is True
    assert "palmeiras" in body["content"].lower()
    assert all("infinitepay" not in citation["url"] for citation in body["citations"])


def test_web_search_for_sao_paulo_news(chat_client: TestClient) -> None:
    response = chat_client.post(
        "/chat",
        json={"message": "Quais as principais notícias de São Paulo hoje?", "user_id": "client-news"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["agent"] == "knowledge"
    assert body["meta"]["rag_used"] is False
    assert body["meta"]["web_search_used"] is True
    assert "são paulo" in body["content"].lower()
    assert len(body["citations"]) >= 2
    assert all("infinitepay" not in citation["url"] for citation in body["citations"])


def test_support_uses_account_status_tool(chat_client: TestClient) -> None:
    response = chat_client.post(
        "/chat",
        json={"message": "Why I am not able to make transfers?", "user_id": "client-support"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["agent"] == "support"
    meta = body["meta"]
    assert meta["ticket_id"] is None
    assert meta.get("account_status")
    assert "account_status" in meta.get("tools_used", [])


def test_support_answers_login_issue_with_faq(chat_client: TestClient) -> None:
    response = chat_client.post(
        "/chat",
        json={"message": "I can't sign in to my account.", "user_id": "client-support"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["agent"] == "support"
    meta = body["meta"]
    assert meta["faq_hit"] is True
    assert meta["ticket_id"] is None
    assert meta["category"] == "acesso"
    assert "faq" in meta.get("tools_used", [])
