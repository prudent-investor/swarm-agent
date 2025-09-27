import time

import pytest

from app.agents.handoff_flow import HandoffFlow
from app.agents.slack_agent import SlackAgent
from app.agents.base import AgentRequest
from app.services.slack.client import MockSlackClient, SlackPayload
from app.services.slack.payloads import SlackContext, build_slack_message
from app.settings import settings


def test_build_slack_message_masks_pii(monkeypatch):
    monkeypatch.setattr(settings, "pii_masking_enabled", True)
    context = SlackContext(
        channel="#test",
        title="[SUPPORT ESCALATION] #TICK PAGAMENTOS/HIGH",
        summary="Cliente com email teste@example.com pediu contato",
        details="Telefone +55 11 91234-5678 esta sem sinal",
        ticket_id="SUP-1",
        category="pagamentos",
        priority="high",
        correlation_id="corr-123",
        links=["https://example.com/ticket/SUP-1"],
        requested_by="cliente@example.com",
    )
    message = build_slack_message(context)
    assert "***@" in message.text
    assert "***" in message.text
    assert "91234" not in message.text


def test_mock_slack_client_returns_result():
    client = MockSlackClient()
    payload = SlackPayload(channel="#test", text="hello", blocks=[])
    result = client.send_message(payload)
    assert result.ok is True
    assert result.channel == "#test"
    assert result.message_id.startswith("mock-")


def test_slack_agent_disabled_flow(monkeypatch):
    flow = HandoffFlow(ttl_seconds=300)
    pending = flow.register(
        correlation_id="corr-x",
        user_id="user-1",
        ticket_id="SUP-123",
        category="pagamentos",
        priority="high",
        summary="Resumo",
        details="Detalhes",
        source="unit",
    )
    monkeypatch.setattr(settings, "slack_enabled", False)
    agent = SlackAgent(slack_client=MockSlackClient(), handoff_flow=flow)
    request = AgentRequest(
        message="sim",
        user_id="user-1",
        metadata={"correlation_id": "corr-2", "handoff_token": pending.token},
    )
    response = agent.run(request)
    assert response.meta["handoff_status"] == "disabled"
    assert response.meta["ticket_id"] == "SUP-123"
    assert "temporariamente indisponivel" in response.content.lower()


def test_slack_agent_request_creates_pending(monkeypatch):
    flow = HandoffFlow(ttl_seconds=300)
    monkeypatch.setattr(settings, "slack_enabled", True)
    agent = SlackAgent(slack_client=MockSlackClient(), handoff_flow=flow)
    request = AgentRequest(
        message="Quero falar com humano",
        user_id="user-5",
        metadata={
            "correlation_id": "corr-req",
            "handoff_action": "request",
            "handoff_summary": "Preciso falar com humano",
            "handoff_details": "Detalhes do problema",
            "handoff_source": "test",
        },
    )
    response = agent.run(request)
    assert response.meta["handoff_status"] == "pending"
    token = response.meta["handoff_token"]
    assert token
    pending = flow.fetch(correlation_id="corr-req", user_id="user-5", token=token)
    assert pending is not None
