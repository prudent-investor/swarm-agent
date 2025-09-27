import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ErrorResponse
from app.services.support_service import SupportService, get_support_service
from app.tools.support.contracts import TicketCreateRequest
from app.tools.support.faq_tool import FAQTool
from app.tools.support.ticket_tool import TicketTool


def _build_service(tmp_path):
    faq_path = tmp_path / "faq.json"
    faq_path.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    ticket_tool = TicketTool(persist_to_file=False, id_factory=lambda: "SUP-API-001")
    faq_tool = FAQTool(dataset_path=faq_path)
    service = SupportService(faq_tool=faq_tool, ticket_tool=ticket_tool)
    ticket = ticket_tool.create(
        TicketCreateRequest(
            summary="Erro de pagamento",
            description="Cliente relata cobranca",
            user_id="cliente@example.com",
            category="pagamentos",
            priority="high",
            escalation=True,
        )
    )
    return service, ticket


@pytest.fixture
def client(tmp_path):
    service, ticket = _build_service(tmp_path)
    app.dependency_overrides[get_support_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client, service, ticket
    app.dependency_overrides.pop(get_support_service, None)


def test_get_ticket_public_success(client):
    test_client, service, ticket = client

    response = test_client.get(f"/support/tickets/{ticket.id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == ticket.id
    assert payload["user_ref"] == "***@example.com"
    assert payload["status"] == "open"
    assert payload["priority"] == "high"


def test_get_ticket_public_not_found(client):
    test_client, service, _ = client

    response = test_client.get("/support/tickets/UNKNOWN")
    assert response.status_code == 404
    payload = response.json()
    assert payload == ErrorResponse(error="ticket_not_found", message="Ticket nao encontrado.").model_dump()
