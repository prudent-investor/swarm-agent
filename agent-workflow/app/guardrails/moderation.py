from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.settings import settings


@dataclass(frozen=True)
class ModerationRule:
    term: str
    category: str
    description: str


_BALANCED_DEFAULT: Tuple[ModerationRule, ...] = (
    ModerationRule("hate speech", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("racist", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("nazi", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("heil hitler", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("national socialism", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("nacional-socialismo", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("death to minorities", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("kill minorities", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("exterminate minorities", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("morte as minorias", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("white power", "hate_speech", "Detected hateful or discriminatory content."),
    ModerationRule("sexual content", "erotic_content", "Detected explicit sexual content."),
    ModerationRule("explicit sexual", "erotic_content", "Detected explicit sexual content."),
    ModerationRule("anal sex", "erotic_content", "Detected explicit sexual content."),
    ModerationRule("sex anal", "erotic_content", "Detected explicit sexual content."),
    ModerationRule("malware", "system_abuse", "Detected a request for malicious tooling."),
    ModerationRule("password", "system_access", "Detected a request for protected credentials."),
    ModerationRule("system password", "system_access", "Detected a request for protected credentials."),
    ModerationRule("senha do sistema", "system_access", "Detected a request for protected credentials."),

)

_STRICT_EXTRA: Tuple[ModerationRule, ...] = (
    ModerationRule("explosive", "violence", "Detected instructions related to explosive materials."),
    ModerationRule("illegal drugs", "illicit_activities", "Detected references to illegal drug creation or trade."),
)


def _blocklist() -> List[ModerationRule]:
    configured = settings.guardrails_moderation_blocklist_terms or ""
    rules: List[ModerationRule] = list(_BALANCED_DEFAULT)
    if settings.guardrails_mode == "strict":
        rules.extend(_STRICT_EXTRA)

    for raw in configured.split(";"):
        term = raw.strip()
        if not term:
            continue
        rules.append(
            ModerationRule(
                term.lower(),
                "custom",
                f"Detected blocked term '{term.lower()}'.",
            )
        )

    unique: List[ModerationRule] = []
    seen: set[str] = set()
    for rule in rules:
        key = rule.term.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(ModerationRule(term=key, category=rule.category, description=rule.description))
    return unique


def _format_safe_message(reason: ModerationRule) -> str:
    category = reason.category.replace("_", " ")
    return (
        "I cannot comply with that request because it violates our policy on "
        f"{category}. {reason.description}"
    )


def moderate_text(text: str) -> Tuple[str, bool, Optional[dict]]:
    if not settings.guardrails_moderation_enabled or settings.guardrails_mode == "off":
        return text, False, None

    lowered = text.lower()
    for term in _blocklist():
        if term.term and term.term in lowered:
            safe_message = _format_safe_message(term)
            reason = {
                "category": term.category,
                "trigger": term.term,
                "description": term.description,
            }
            return safe_message, True, reason
    return text, False, None
