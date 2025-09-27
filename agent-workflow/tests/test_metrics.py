from typing import Dict

import pytest
from fastapi.testclient import TestClient

from app.agents.base import AgentRequest, AgentResponse, Route, RoutingDecision
from app.main import app
from app.observability.metrics import get_metrics_registry
from app.routers import chat as chat_router


class MetricsRouter:
    def route_message(self, message: str) -> RoutingDecision:
        if "redirect" in message:
            return RoutingDecision(route=Route.custom, hint="custom", confidence=0.1)
        return RoutingDecision(route=Route.knowledge, hint="docs", confidence=0.9)


class MetricsStubAgent:
    def __init__(self, name: str):
        self.name = name

    def run(self, request: AgentRequest) -> AgentResponse:
        meta: Dict[str, object] = {"source": self.name}
        return AgentResponse(agent=self.name, content=f"handled:{self.name}", citations=[], meta=meta)


@pytest.fixture(autouse=True)
def reset_metrics_registry() -> None:
    registry = get_metrics_registry()
    registry.reset()
    yield
    registry.reset()


@pytest.fixture
def metrics_client() -> TestClient:
    app.dependency_overrides[chat_router.get_router_agent] = lambda: MetricsRouter()

    def _factory():
        return {
            Route.knowledge: MetricsStubAgent("knowledge"),
            Route.support: MetricsStubAgent("support"),
            Route.custom: MetricsStubAgent("custom"),
            Route.slack: MetricsStubAgent("slack"),
        }

    app.dependency_overrides[chat_router.get_agents] = _factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(chat_router.get_router_agent, None)
    app.dependency_overrides.pop(chat_router.get_agents, None)


def test_metrics_endpoint_reports_counters(metrics_client: TestClient) -> None:
    chat_response = metrics_client.post("/chat", json={"message": "olá", "user_id": "client"})
    assert chat_response.status_code == 200
    correlation_id = chat_response.json()["correlation_id"]

    metrics_response = metrics_client.get("/metrics")
    assert metrics_response.status_code == 200
    body = metrics_response.text

    assert 'chat_requests_total{agent="knowledge"} 1' in body
    assert 'chat_requests_total{agent="support"} 0' in body
    assert 'chat_redirect_total 0' in body
    assert f'correlation_id="{correlation_id}"' in body


def test_metrics_latency_bucket_for_slow_request(metrics_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    values = [100.0, 100.8]
    index = {"i": 0}

    class FakeTimer:
        @staticmethod
        def perf_counter() -> float:
            current = values[min(index["i"], len(values) - 1)]
            index["i"] += 1
            return current

    monkeypatch.setattr("app.observability.tracing.time", FakeTimer())

    chat_response = metrics_client.post("/chat", json={"message": "ola lento", "user_id": "client"})
    assert chat_response.status_code == 200
    correlation_id = chat_response.json()["correlation_id"]

    metrics_text = metrics_client.get("/metrics").text
    expected = f'chat_request_latency_ms_bucket{{le="1000", correlation_id="{correlation_id}"}} 1'
    assert expected in metrics_text
