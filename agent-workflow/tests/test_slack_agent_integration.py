import pytest
from fastapi.testclient import TestClient

from app.agents.handoff_flow import HandoffFlow
from app.agents.slack_agent import SlackAgent
from app.main import app
from app.routers import chat as chat_router
from app.services.slack.client import MockSlackClient
from app.settings import settings


@pytest.fixture(autouse=True)
def override_handoff(monkeypatch):
    flow = HandoffFlow(ttl_seconds=300)
    slack_agent = SlackAgent(slack_client=MockSlackClient(), handoff_flow=flow)
    monkeypatch.setattr(chat_router, "_handoff_flow", flow)
    monkeypatch.setattr(chat_router, "_slack_agent", slack_agent)
    monkeypatch.setattr(settings, "slack_enabled", True)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_support_escalation_to_slack_flow(client):
    first = client.post(
        "/chat",
        json={"message": "Estou com fraude e cobranca duplicada urgente", "user_id": "cli-99"},
    )
    assert first.status_code == 200
    payload1 = first.json()
    assert payload1["agent"] == "support"
    meta1 = payload1["meta"]
    token = meta1["handoff_token"]
    assert meta1["handoff_status"] == "pending"

    second = client.post(
        "/chat",
        json={
            "message": "sim",
            "user_id": "cli-99",
            "metadata": {"handoff_token": token},
        },
    )
    assert second.status_code == 200
    payload2 = second.json()
    assert payload2["agent"] == "slack"
    meta2 = payload2["meta"]
    assert meta2["handoff_status"] == "ok"
    assert meta2["handoff_message_id"].startswith("mock-")


def test_direct_handoff_confirmation_flow(client):
    initial = client.post(
        "/chat",
        json={"message": "Quero falar com humano imediatamente", "user_id": "cli-100"},
    )
    assert initial.status_code == 200
    payload = initial.json()
    assert payload["agent"] == "slack"
    meta = payload["meta"]
    token = meta["handoff_token"]
    assert meta["handoff_status"] == "pending"

    follow = client.post(
        "/chat",
        json={
            "message": "sim",
            "user_id": "cli-100",
            "metadata": {"handoff_token": token},
        },
    )
    assert follow.status_code == 200
    payload_follow = follow.json()
    assert payload_follow["agent"] == "slack"
    assert payload_follow["meta"]["handoff_status"] == "ok"
