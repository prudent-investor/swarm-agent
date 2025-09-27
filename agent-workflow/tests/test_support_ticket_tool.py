from pathlib import Path

from app.tools.support.contracts import TicketCreateRequest
from app.tools.support.ticket_tool import TicketTool


def test_ticket_tool_creates_and_retrieves_ticket(monkeypatch):
    tool = TicketTool(persist_to_file=False, id_factory=lambda: "SUP-TEST-001")

    ticket = tool.create(
        TicketCreateRequest(
            summary="Pagamento nao compensado",
            description="Cliente relata pagamento atrasado",
            user_id="user-123",
            category="pagamentos",
            priority="medium",
        )
    )

    stored = tool.get(ticket.id)
    assert stored is not None
    assert stored.id == "SUP-TEST-001"
    assert stored.created_at.tzinfo is not None
    assert stored.priority == "medium"


def test_ticket_tool_list_by_user(monkeypatch):
    tool = TicketTool(persist_to_file=False, id_factory=lambda: "SUP-TEST-002")

    tool.create(
        TicketCreateRequest(
            summary="Erro de acesso",
            description="Nao consigo acessar",
            user_id="user-abc",
            category="acesso",
            priority="high",
        )
    )

    tickets = tool.list_by_user("user-abc")
    assert len(tickets) == 1
    assert tickets[0].category == "acesso"


def test_ticket_tool_persists_to_file(tmp_path):
    storage: Path = tmp_path / "tickets.json"
    tool = TicketTool(persist_to_file=True, file_path=storage, id_factory=lambda: "SUP-PERSIST-001")

    ticket = tool.create(
        TicketCreateRequest(
            summary="Maquininha travada",
            description="Sem conexao",
            user_id="user-z",
            category="dispositivo",
            priority="high",
            escalation=True,
        )
    )

    assert storage.exists()
    data = storage.read_text(encoding="utf-8")
    assert "SUP-PERSIST-001" in data

    reloaded = TicketTool(persist_to_file=True, file_path=storage)
    stored = reloaded.get(ticket.id)
    assert stored is not None
    assert stored.escalation is True
