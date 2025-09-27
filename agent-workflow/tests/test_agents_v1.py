import pytest
from types import SimpleNamespace

from app.agents.base import AgentControlledError, AgentRequest
from app.agents.custom_agent import CustomAgent
from app.agents.support_agent import CustomerSupportAgent


class StubSupportService:
    def handle_support(self, message: str, user_id: str | None, correlation_id: str):
        ticket = SimpleNamespace(
            id="SUP-000",
            summary="Resumo",
            description=message,
            category="pagamentos",
            priority="medium",
            escalation=False,
        )
        policy = SimpleNamespace(category="pagamentos", priority="medium", escalation=False)
        return {
            "faq_result": None,
            "ticket": ticket,
            "policy": policy,
            "latency_ms": 1.0,
        }


class StubFailureService:
    def handle_support(self, *args, **kwargs):
        raise RuntimeError("boom")


class StubLLMProvider:
    def __init__(self, text: str = "Resposta generica.") -> None:
        self._text = text

    def generate_response(self, **_: object) -> str:
        return self._text


@pytest.mark.parametrize(
    "agent,expected_name",
    [
        (CustomerSupportAgent(service=StubSupportService()), "support"),
        (CustomAgent(StubLLMProvider()), "custom_agent_v1"),
    ],
)
def test_agent_returns_structured_response(agent, expected_name):
    result = agent.run(AgentRequest(message="teste", user_id="user-1"))

    assert result.agent == expected_name
    assert isinstance(result.citations, list)
    assert result.meta is not None


def test_support_agent_handles_service_failure():
    agent = CustomerSupportAgent(service=StubFailureService())

    with pytest.raises(AgentControlledError) as exc:
        agent.run(AgentRequest(message="falha"))

    assert exc.value.status_code == 503
    assert exc.value.agent == agent.name
