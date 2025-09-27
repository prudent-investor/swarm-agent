import itertools
import json

import pytest

from app.agents.base import AgentRequest
from app.agents.support_agent_v2 import CustomerSupportAgent
from app.services.support_service import SupportService
from app.settings import settings
from app.tools.support.faq_tool import FAQTool
from app.tools.support.ticket_tool import TicketTool


@pytest.fixture
def support_agent(tmp_path, monkeypatch):
    dataset = [
        {
            "id": "faq-1",
            "pergunta": "Como redefinir a senha?",
            "resposta": "Acesse esqueci minha senha e siga o passo a passo.",
            "tags": ["senha", "acesso"],
            "categoria": "acesso",
            "atualizado_em": "2025-08-01",
        }
    ]
    path = tmp_path / "faq.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(settings, "support_faq_enabled", True)
    monkeypatch.setattr(settings, "support_faq_score_threshold", 0.2)
    monkeypatch.setattr(settings, "support_max_response_chars", 200)
    monkeypatch.setattr(settings, "support_escalation_auto", False)

    counter = itertools.count(1)

    def _id_factory():
        return f"SUP-IT-{next(counter):03d}"

    ticket_tool = TicketTool(persist_to_file=False, id_factory=_id_factory)
    faq_tool = FAQTool(dataset_path=path)
    service = SupportService(faq_tool=faq_tool, ticket_tool=ticket_tool)
    agent = CustomerSupportAgent(service=service)
    return agent, service


def test_support_agent_answers_with_faq(support_agent):
    agent, service = support_agent

    response = agent.run(
        AgentRequest(message="Preciso redefinir minha senha de acesso", user_id="cli-1", metadata={"correlation_id": "corr-1"})
    )

    assert response.meta["faq_hit"] is True
    assert response.meta["ticket_id"] is None
    assert "senha" in response.content.lower()
    assert service.metrics.faq_hits == 1


def test_support_agent_creates_ticket_when_no_faq_hit(support_agent):
    agent, service = support_agent

    response = agent.run(
        AgentRequest(message="Minha maquininha travou sem conexao", user_id="cli-2", metadata={"correlation_id": "corr-2"})
    )

    assert response.meta["faq_hit"] is False
    assert response.meta["ticket_id"].startswith("SUP-IT-")
    assert response.meta["category"] == "dispositivo"
    assert service.metrics.tickets_created == 1


def test_support_agent_flags_escalation_for_critical_case(support_agent, monkeypatch):
    agent, service = support_agent
    monkeypatch.setattr(settings, "support_escalation_auto", True)

    response = agent.run(
        AgentRequest(
            message="Estou com cobranca duplicada e preciso falar com humano URGENTE",
            user_id="cli-3",
            metadata={"correlation_id": "corr-3"},
        )
    )

    assert response.meta["escalation_suggested"] is True
    assert response.meta["priority"] in {"critical", "high"}
    assert service.metrics.escalations >= 1


def test_support_agent_respects_response_limit(support_agent, monkeypatch):
    agent, _ = support_agent
    monkeypatch.setattr(settings, "support_max_response_chars", 60)

    response = agent.run(
        AgentRequest(
            message="Problema recorrente: meu aplicativo nao funciona e preciso de ajuda novamente imediatamente",
            user_id="cli-4",
            metadata={"correlation_id": "corr-4"},
        )
    )

    assert len(response.content) <= 60
