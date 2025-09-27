import pytest

from app.agents.support_policies import decide
from app.settings import settings


@pytest.mark.parametrize(
    "message,expected_priority",
    [
        ("Estou com cobranca duplicada e isso e urgente", "critical"),
        ("Nao consigo acessar minha conta ha horas", "high"),
        ("Gostaria de atualizar dados cadastrais", "low"),
    ],
)
def test_support_policies_priority(message, expected_priority, monkeypatch):
    monkeypatch.setattr(settings, "support_escalation_auto", False)
    decision = decide(message)
    assert decision.priority == expected_priority


def test_support_policies_escalation_for_high_priority(monkeypatch):
    monkeypatch.setattr(settings, "support_escalation_auto", True)
    decision = decide("Nao consigo acessar minha conta, preciso falar com humano")
    assert decision.escalation is True
    assert decision.category == "acesso"


def test_support_policies_escalation_on_repeat_issue(monkeypatch):
    monkeypatch.setattr(settings, "support_escalation_auto", False)
    decision = decide("Esse problema acontece de novo, nada resolvido")
    assert decision.escalation is True
    assert decision.priority in {"low", "medium"}
