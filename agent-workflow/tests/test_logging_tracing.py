import pytest
from fastapi.testclient import TestClient

from app.agents.base import AgentRequest, AgentResponse, Route, RoutingDecision
from app.main import app
from app.routers import chat as chat_router


class LoggingRouter:
    def route_message(self, message: str) -> RoutingDecision:
        return RoutingDecision(route=Route.knowledge, hint="docs", confidence=0.9)


class LoggingAgent:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(agent=self.name, content="handled", citations=[], meta={})


@pytest.fixture
def logging_client() -> TestClient:
    app.dependency_overrides[chat_router.get_router_agent] = lambda: LoggingRouter()

    def _factory():
        return {
            Route.knowledge: LoggingAgent("knowledge"),
            Route.support: LoggingAgent("support"),
            Route.custom: LoggingAgent("custom"),
            Route.slack: LoggingAgent("slack"),
        }

    app.dependency_overrides[chat_router.get_agents] = _factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(chat_router.get_router_agent, None)
    app.dependency_overrides.pop(chat_router.get_agents, None)


def test_correlation_id_propagated_to_logs(logging_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO"):
        response = logging_client.post(
            "/chat",
            json={"message": "Preciso de dados", "user_id": "user-1"},
            headers={"X-Correlation-ID": "abc123"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["correlation_id"] == "abc123"
    assert payload["meta"]["correlation_id"] == "abc123"
    assert response.headers["X-Correlation-ID"] == "abc123"

    success_record = next(record for record in caplog.records if record.getMessage() == "chat.success")
    assert success_record.correlation_id == "abc123"
    assert success_record.route == "knowledge"
    assert success_record.agent == "knowledge"
    assert isinstance(success_record.flags, dict)


def test_generates_correlation_id_when_missing(logging_client: TestClient) -> None:
    response = logging_client.post("/chat", json={"message": "Outra pergunta", "user_id": "user-2"})

    assert response.status_code == 200
    payload = response.json()
    generated_id = payload["correlation_id"]
    assert generated_id
    assert payload["meta"]["correlation_id"] == generated_id
    assert response.headers["X-Correlation-ID"] == generated_id
