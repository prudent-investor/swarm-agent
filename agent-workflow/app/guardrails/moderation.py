from __future__ import annotations

from typing import List, Tuple

from app.settings import settings

_BALANCED_DEFAULT = ["conteudo proibido", "odio", "violencia", "autolesao"]
_STRICT_EXTRA = ["explosivo", "instrucoes perigosas", "malware", "drogas ilegais"]


def _blocklist() -> List[str]:
    configured = settings.guardrails_moderation_blocklist_terms or ""
    custom = [term.strip().lower() for term in configured.split(";") if term.strip()]
    base = [term.lower() for term in _BALANCED_DEFAULT]
    if settings.guardrails_mode == "strict":
        base.extend(term.lower() for term in _STRICT_EXTRA)
    base.extend(custom)
    return list({term for term in base if term})


def moderate_text(text: str) -> Tuple[str, bool, str | None]:
    if not settings.guardrails_moderation_enabled or settings.guardrails_mode == "off":
        return text, False, None

    lowered = text.lower()
    for term in _blocklist():
        if term and term in lowered:
            safe_message = "Por seguranca, nao posso responder a esse pedido no momento."
            return safe_message, True, term
    return text, False, None
