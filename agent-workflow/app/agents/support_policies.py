from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.settings import settings

CATEGORY_TERMS = {
    "pagamentos": ["pagamento", "cobranca", "fatura", "credito", "debito", "boleto"],
    "acesso": ["acesso", "acessar", "login", "senha", "entrar", "bloqueado"],
    "dispositivo": ["maquininha", "pos", "terminal", "tap to pay", "tap"],
    "conta": ["cadastro", "conta", "dados", "perfil", "atualizar cadastro"],
}

SEVERITY_TERMS = {
    "critical": [
        "queda geral",
        "fora do ar",
        "indisponivel",
        "fraude",
        "cobranca duplicada",
        "vazamento",
    ],
    "high": [
        "nao consigo acessar",
        "nao recebi",
        "pagamento travado",
        "erro geral",
    ],
}

ESCALATION_REQUEST_TERMS = ["falar com humano", "atendente", "suporte humano", "pessoa"]
REPEAT_ISSUE_TERMS = ["de novo", "novamente", "mais uma vez", "continua", "nada resolvido"]


@dataclass
class PolicyDecision:
    category: str
    priority: str
    escalation: bool


def _terms_from_env(env_value: str | None) -> Dict[str, list[str]]:
    overrides: Dict[str, list[str]] = {}
    if not env_value:
        return overrides
    for pair in env_value.split(";"):
        if not pair:
            continue
        if ":" not in pair:
            continue
        key, terms = pair.split(":", 1)
        overrides[key.strip().lower()] = [term.strip().lower() for term in terms.split(",") if term.strip()]
    return overrides


CATEGORY_TERMS.update(_terms_from_env(settings.support_category_terms_overrides))
SEVERITY_CUSTOM = _terms_from_env(settings.support_severity_terms_overrides)
for level, terms in SEVERITY_CUSTOM.items():
    bucket = SEVERITY_TERMS.setdefault(level.lower(), [])
    bucket.extend(terms)


def classify_category(message: str) -> str:
    text = message.lower()
    for category, terms in CATEGORY_TERMS.items():
        if any(term in text for term in terms):
            return category
    return "outros"


def classify_priority_and_escalation(message: str) -> tuple[str, bool]:
    text = message.lower()
    for term in SEVERITY_TERMS.get("critical", []):
        if term in text:
            return "critical", True
    for term in SEVERITY_TERMS.get("high", []):
        if term in text:
            return "high", True
    if "nao funciona" in text or "nao consigo" in text:
        return "medium", False
    return "low", False


def _has_request_for_human(text: str) -> bool:
    return any(term in text for term in ESCALATION_REQUEST_TERMS)


def _looks_like_repeat_issue(text: str) -> bool:
    return any(term in text for term in REPEAT_ISSUE_TERMS)


def decide(message: str) -> PolicyDecision:
    text = message.lower()
    category = classify_category(text)
    priority, base_escalation = classify_priority_and_escalation(text)

    escalation = base_escalation
    if _has_request_for_human(text) or _looks_like_repeat_issue(text):
        escalation = True
    if settings.support_escalation_auto and priority in {"critical", "high"}:
        escalation = True

    return PolicyDecision(category=category, priority=priority, escalation=escalation)

