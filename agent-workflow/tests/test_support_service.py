from datetime import datetime, timezone

import pytest

from app.agents.support_policies import PolicyDecision
from app.services.support_service import SupportMetrics, SupportService, _mask_pii
from app.tools.support import FAQItem, FAQResult, Ticket


class FAQStub:
    def __init__(self, result: FAQResult | None) -> None:
        self._result = result
        self.queries: list[str] = []

    def search(self, query):  # type: ignore[override]
        self.queries.append(query.message)
        return self._result


class TicketStub:
    def __init__(self, ticket: Ticket | None, *, fail_on_create: bool = False) -> None:
        self._ticket = ticket
        self.fail_on_create = fail_on_create
        self.created_requests = []

    def create(self, request):  # type: ignore[override]
        if self.fail_on_create:
            raise AssertionError("create should not be called")
        self.created_requests.append(request)
        if self._ticket is None:
            raise AssertionError("ticket fixture not provided")
        return self._ticket

    def get(self, ticket_id: str):  # type: ignore[override]
        if self._ticket and ticket_id == self._ticket.id:
            return self._ticket
        return None

    def list_by_user(self, user_id: str):  # type: ignore[override]
        if self._ticket and self._ticket.user_id == user_id:
            return [self._ticket]
        return []


@pytest.fixture
def sample_ticket() -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        id="SUP-1",
        summary="Pagamento nao processado",
        description="Detalhes",
        user_id="cliente@example.com",
        status="open",
        priority="high",
        category="pagamentos",
        channel="chat",
        created_at=now,
        updated_at=now,
        escalation=True,
    )


def test_support_metrics_tracks_latency_and_p95():
    metrics = SupportMetrics(max_samples=3)

    metrics.add_latency(10.0)
    metrics.add_latency(20.0)
    metrics.add_latency(30.0)
    metrics.add_latency(40.0)  # pushes out the first value

    assert metrics.latencies_ms == [20.0, 30.0, 40.0]
    assert metrics.average_latency_ms == pytest.approx(30.0)
    assert metrics.p95_latency_ms == pytest.approx(30.0)


def test_mask_pii_masks_emails_and_numbers(monkeypatch):
    monkeypatch.setattr("app.settings.settings.support_pii_masking_enabled", True, raising=False)

    value = "cliente@empresa.com pediu suporte para pedido 123456789 e telefone 5511987654321"
    masked = _mask_pii(value)

    assert "cliente@empresa.com" not in masked
    assert masked.count("***") >= 2
    assert masked.startswith("***@empresa.com")


def test_mask_pii_respects_disabled_setting(monkeypatch):
    monkeypatch.setattr("app.settings.settings.support_pii_masking_enabled", False, raising=False)

    value = "cliente@empresa.com"
    assert _mask_pii(value) == value


def test_handle_support_returns_faq_result(monkeypatch):
    monkeypatch.setattr("app.settings.settings.support_faq_enabled", True, raising=False)

    faq_item = FAQItem(
        id="faq-1",
        pergunta="Como recuperar a senha?",
        resposta="Use a opcao esqueci minha senha",
        tags=["senha"],
        categoria="acesso",
        atualizado_em="2024-01-01",
    )
    faq_result = FAQResult(item=faq_item, score=0.9, explanation="matched by senha")
    faq_tool = FAQStub(faq_result)
    ticket_tool = TicketStub(ticket=None, fail_on_create=True)

    service = SupportService(faq_tool=faq_tool, ticket_tool=ticket_tool)
    response = service.handle_support("Preciso de ajuda com senha", "cliente@example.com", "corr-1")

    assert response["faq_result"] == faq_result
    assert response["ticket"] is None
    assert response["policy"] is None
    assert response["latency_ms"] > 0
    assert service.metrics.total_requests == 1
    assert service.metrics.faq_hits == 1
    assert service.metrics.latencies_ms


def test_handle_support_creates_ticket_and_records_metrics(monkeypatch, sample_ticket):
    monkeypatch.setattr("app.settings.settings.support_faq_enabled", False, raising=False)

    policy = PolicyDecision(category="pagamentos", priority="critical", escalation=True)
    monkeypatch.setattr("app.services.support_service.decide", lambda _msg: policy)

    ticket_tool = TicketStub(ticket=sample_ticket)
    service = SupportService(faq_tool=FAQStub(result=None), ticket_tool=ticket_tool)

    message = "   Pagamento travado no caixa. Preciso falar com humano imediatamente.   "
    response = service.handle_support(message, sample_ticket.user_id, "corr-2")

    assert response["ticket"] == sample_ticket
    assert response["policy"] == policy
    assert service.metrics.tickets_created == 1
    assert service.metrics.escalations == 1
    assert response["latency_ms"] > 0

    assert ticket_tool.created_requests, "Ticket create should have been called"
    request = ticket_tool.created_requests[0]
    assert request.summary == "Pagamento travado no caixa"
    assert "Preciso falar com humano" in request.description


def test_get_ticket_public_masks_user_reference(monkeypatch, sample_ticket):
    monkeypatch.setattr("app.settings.settings.support_pii_masking_enabled", True, raising=False)
    ticket_tool = TicketStub(ticket=sample_ticket)

    service = SupportService(faq_tool=FAQStub(result=None), ticket_tool=ticket_tool)

    view = service.get_ticket_public(sample_ticket.id)
    assert view is not None
    assert view.id == sample_ticket.id
    assert view.user_ref == "***@example.com"

    empty_view = service.get_ticket_public("unknown")
    assert empty_view is None


def test_list_tickets_by_user(sample_ticket):
    ticket_tool = TicketStub(ticket=sample_ticket)
    service = SupportService(faq_tool=FAQStub(result=None), ticket_tool=ticket_tool)

    tickets = service.list_tickets_by_user(sample_ticket.user_id)
    assert tickets == [sample_ticket]

    assert not service.list_tickets_by_user("outro")
