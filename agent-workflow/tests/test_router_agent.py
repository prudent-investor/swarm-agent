from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.agents.base import Route, RoutingDecision
from app.agents.router_agent import RouterAgent
from app.main import app
from app.routers.router_agent import get_router_agent
from app.settings import settings


class MockRouterAgent:
    def route_message(self, message: str) -> RoutingDecision:
        text = message.lower()
        if "humano" in text:
            return RoutingDecision(route=Route.slack, hint="handoff")
        if "privacidade" in text or "document" in text:
            return RoutingDecision(route=Route.knowledge, hint="Refer to docs")
        if "pagamento" in text or "suporte" in text or "cartao" in text:
            return RoutingDecision(route=Route.support, hint="Escalate to support")
        return RoutingDecision(route=Route.custom, hint="General inquiry")


@pytest.fixture(autouse=True)
def override_router_agent() -> Generator[None, None, None]:
    def _factory() -> MockRouterAgent:
        return MockRouterAgent()

    app.dependency_overrides[get_router_agent] = _factory
    yield
    app.dependency_overrides.pop(get_router_agent, None)


@pytest.mark.parametrize(
    "message,expected_route",
    [
        ("Qual a politica de privacidade da empresa?", Route.knowledge.value),
        ("Estou com um problema no pagamento da minha assinatura", Route.support.value),
        ("Preciso de ajuda com o cart\u00e3o", Route.support.value),
        ("Ola, tudo bem?", Route.custom.value),
        ("Quero falar com humano agora", Route.slack.value),
    ],
)
def test_route_endpoint_returns_expected_route(message: str, expected_route: str) -> None:
    with TestClient(app) as client:
        response = client.post("/route", json={"message": message})

    assert response.status_code == 200

    payload = response.json()
    assert payload["route"] == expected_route
    assert payload["route"] in {route.value for route in Route}


def test_router_agent_matches_direct_handoff_without_api(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    router = RouterAgent(api_key=None)

    decision = router.route_message("Preciso falar com um atendente humano")
    assert decision.route is Route.slack
    assert decision.hint == "user_requested_human"


@pytest.mark.parametrize(
    "message,expected_route",
    [
        ("Qual e a politica de privacidade?", Route.knowledge),
        ("Estou com problema no pagamento", Route.support),
        ("Ola bom dia", Route.custom),
    ],
)
def test_router_fallback_handles_messages_without_accents(monkeypatch, message: str, expected_route: Route):
    monkeypatch.setattr(settings, "openai_api_key", None)
    router = RouterAgent(api_key=None)

    decision = router.route_message(message)
    assert decision.route is expected_route
