from app.agents.base import AgentRequest
from app.agents.handoff_flow import HandoffFlow
from app.agents.slack_agent import SlackAgent
from app.services.slack.client import MockSlackClient
from app.settings import settings


def test_slack_agent_forwards_request_to_humans(monkeypatch) -> None:
    monkeypatch.setattr(settings, "slack_agent_enabled", True)
    flow = HandoffFlow(ttl_seconds=60)
    agent = SlackAgent(slack_client=MockSlackClient(), handoff_flow=flow)

    request = AgentRequest(
        message="I want to talk to a human",
        user_id="user-42",
        metadata={
            "correlation_id": "corr-test",
            "handoff_action": "request",
            "handoff_summary": "I want to talk to a human",
            "handoff_details": "I have an issue with my account",
        },
    )

    response = agent.run(request)

    assert response.agent == "slack"
    assert response.meta["channel"] == settings.slack_channel_default
    assert response.meta["handoff_status"] == "pending"
    assert response.meta["redirected"] is True
