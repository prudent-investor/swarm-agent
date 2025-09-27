import pytest

from app.agents.base import Route
from app.services.redirect_service import RedirectService
from app.settings import settings


@pytest.fixture
def redirect_service():
    return RedirectService()


def test_redirect_service_manual_redirect(monkeypatch, redirect_service: RedirectService) -> None:
    monkeypatch.setattr(settings, "redirect_enabled", True)
    monkeypatch.setattr(settings, "guardrails_redirect_always", True)

    result = redirect_service.evaluate(
        message="Preciso de ajuda",
        route=Route.knowledge,
        confidence=0.9,
        user_id="cli-123",
        metadata=None,
    )

    assert result is not None
    assert result.reason == "manual"
    response = result.response
    assert response.agent == "redirect"
    assert response.meta["redirect_reason"] == "manual"
    assert response.meta["channel"] == settings.slack_channel_default
    assert response.meta["user_id"] == "cli-123"


def test_redirect_service_low_confidence(monkeypatch, redirect_service: RedirectService) -> None:
    monkeypatch.setattr(settings, "redirect_enabled", True)
    monkeypatch.setattr(settings, "guardrails_redirect_always", False)
    monkeypatch.setattr(settings, "redirect_confidence_threshold", 0.4)

    result = redirect_service.evaluate(
        message="Resposta duvidosa",
        route=Route.support,
        confidence=0.2,
        user_id=None,
        metadata=None,
    )

    assert result is not None
    assert result.reason == "low_confidence"
    response = result.response
    assert response.meta["redirect_reason"] == "low_confidence"
    assert response.meta["ticket_id"].startswith("HUM-")


def test_redirect_service_disabled(monkeypatch, redirect_service: RedirectService) -> None:
    monkeypatch.setattr(settings, "redirect_enabled", False)

    result = redirect_service.evaluate(
        message="Quero um humano",
        route=Route.custom,
        confidence=0.1,
        user_id="cli-9",
        metadata=None,
    )

    assert result is None
