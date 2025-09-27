import pytest
from fastapi.testclient import TestClient

from app.agents.base import AgentRequest, AgentResponse, Route, RoutingDecision
from app.main import app
from app.routers import chat as chat_router
from app.settings import settings


class DummyRouter:
    def route_message(self, message: str) -> RoutingDecision:
        text = message.lower()
        if "politica" in text:
            return RoutingDecision(route=Route.knowledge, hint="docs")
        if "pagamento" in text:
            return RoutingDecision(route=Route.support, hint="support")
        if "humano" in text:
            return RoutingDecision(route=Route.slack, hint="handoff")
        return RoutingDecision(route=Route.custom, hint="custom")


class StubAgent:
    def __init__(self, name: str, content: str):
        self.name = name
        self._content = content

    def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(
            agent=self.name,
            content=self._content,
            citations=[{"title": "Base", "url": "https://www.infinitepay.io", "source_type": "infinitepay"}],
            meta={"rag_used": self.name == "knowledge"},
        )


@pytest.fixture(autouse=True)
def override_dependencies() -> None:
    app.dependency_overrides[chat_router.get_router_agent] = lambda: DummyRouter()

    def _factory():
        return {
            Route.knowledge: StubAgent("knowledge", "Resposta de conhecimento."),
            Route.support: StubAgent("support_agent_v1", "Resposta de suporte."),
            Route.custom: StubAgent("custom_agent_v1", "Resposta generica."),
            Route.slack: StubAgent("slack", "Confirmacao pendente."),
        }

    app.dependency_overrides[chat_router.get_agents] = _factory
    yield
    app.dependency_overrides.pop(chat_router.get_router_agent, None)
    app.dependency_overrides.pop(chat_router.get_agents, None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "message,expected_agent",
    [
        ("Qual a politica de privacidade da empresa?", "knowledge"),
        ("Estou com problema no pagamento", "support_agent_v1"),
        ("Ola, tudo bem?", "custom_agent_v1"),
        ("Quero falar com humano", "slack"),
    ],
)
def test_chat_endpoint_routes_to_expected_agent(client: TestClient, message: str, expected_agent: str) -> None:
    response = client.post("/chat", json={"message": message, "user_id": "user-42"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["agent"] == expected_agent
    assert isinstance(payload["citations"], list)
    assert payload["citations"][0]["url"].startswith("https://")
    assert payload["meta"]["route"] in {route.value for route in Route}
    assert "latency_ms" in payload["meta"]
    assert payload["correlation_id"]


def test_chat_endpoint_rejects_invalid_payload(client: TestClient) -> None:
    response = client.post("/chat", json={"user_id": "user-42"})
    assert response.status_code == 422




def test_chat_guardrails_meta_flags(client: TestClient) -> None:
    response = client.post(
        "/chat", json={"message": "Quero falar com o cartão humano", "user_id": "cli-10"}
    )

    assert response.status_code == 200
    payload = response.json()
    meta = payload["meta"]

    assert meta["guardrails_mode"] == settings.guardrails_mode
    assert meta["guardrails_accents_stripped"] is True
    assert meta.get("moderation_blocked") is False
    assert meta.get("guardrails_pre_ms") is not None
