import json

import pytest

from app.settings import settings
from app.tools.support.faq_tool import FAQTool, FAQQuery


@pytest.fixture
def faq_dataset(tmp_path):
    path = tmp_path / "faq.json"
    payload = [
        {
            "id": "item-1",
            "pergunta": "Como recuperar a senha?",
            "resposta": "Use o link de esqueci minha senha e siga as instrucoes.",
            "tags": ["senha", "acesso"],
            "categoria": "acesso",
            "atualizado_em": "2025-09-01",
        },
        {
            "id": "item-2",
            "pergunta": "Cobranca duplicada no pagamento",
            "resposta": "Verifique o extrato e abra um ticket.",
            "tags": ["cobranca", "pagamento"],
            "categoria": "pagamentos",
            "atualizado_em": "2025-09-02",
        },
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_faq_tool_returns_best_match(faq_dataset, monkeypatch):
    monkeypatch.setattr(settings, "support_faq_score_threshold", 0.2)
    tool = FAQTool(dataset_path=faq_dataset)

    result = tool.search(FAQQuery("Esqueci completamente minha senha de acesso"))

    assert result is not None
    assert result.item.id == "item-1"
    assert result.score >= 0.2
    assert "senha" in result.explanation


def test_faq_tool_respects_threshold(faq_dataset, monkeypatch):
    monkeypatch.setattr(settings, "support_faq_score_threshold", 0.9)
    tool = FAQTool(dataset_path=faq_dataset)

    result = tool.search(FAQQuery("Preciso de ajuda com senha"))

    assert result is None


def test_faq_tool_scores_by_tags(faq_dataset, monkeypatch):
    monkeypatch.setattr(settings, "support_faq_score_threshold", 0.3)
    tool = FAQTool(dataset_path=faq_dataset)

    result = tool.search(FAQQuery("Problema de cobranca no pagamento"))

    assert result is not None
    assert result.item.categoria == "pagamentos"
    assert result.score >= 0.3
