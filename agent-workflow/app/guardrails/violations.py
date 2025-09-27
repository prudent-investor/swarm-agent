from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class GuardrailViolation:
    category: str
    trigger: str
    description: str

    def as_dict(self) -> dict:
        return {
            "category": self.category,
            "trigger": self.trigger,
            "description": self.description,
        }


@dataclass(frozen=True)
class KeywordRule:
    category: str
    description: str
    keywords: Sequence[str]


_KEYWORD_RULES: Tuple[KeywordRule, ...] = (
    KeywordRule(
        category="hate_speech",
        description="Detected hateful or discriminatory language.",
        keywords=("hate speech", "racist", "bigot", "white supremacy", "genocide"),
    ),
    KeywordRule(
        category="erotic_content",
        description="Detected explicit sexual content.",
        keywords=("sexual act", "porn", "explicit sexual", "nsfw", "erotic roleplay"),
    ),
    KeywordRule(
        category="system_access",
        description="Detected a request for system access or credentials.",
        keywords=(
            "admin password",
            "system password",
            "root password",
            "ssh key",
            "database credentials",
        ),
    ),
    KeywordRule(
        category="payment_data",
        description="Detected a request involving payment card information.",
        keywords=("credit card", "card number", "cvv", "iban", "routing number"),
    ),
    KeywordRule(
        category="personal_identifiers",
        description="Detected a request for personal identification numbers.",
        keywords=(
            "social security",
            "ssn",
            "passport number",
            "driver's license",
            "national id",
        ),
    ),
)


CARD_NUMBER_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def detect_keyword_violations(text: str) -> List[GuardrailViolation]:
    lowered = text.lower()
    violations: List[GuardrailViolation] = []
    seen: Set[tuple[str, str]] = set()
    for rule in _KEYWORD_RULES:
        for keyword in rule.keywords:
            if keyword and keyword in lowered:
                key = (rule.category, keyword)
                if key in seen:
                    continue
                seen.add(key)
                violations.append(
                    GuardrailViolation(
                        category=rule.category,
                        trigger=keyword,
                        description=rule.description,
                    )
                )
                break
    return violations


def detect_pattern_violations(text: str) -> List[GuardrailViolation]:
    violations: List[GuardrailViolation] = []
    if CARD_NUMBER_RE.search(text):
        violations.append(
            GuardrailViolation(
                category="payment_data",
                trigger="potential_card_number",
                description="Detected a sequence resembling a payment card number.",
            )
        )
    if SSN_RE.search(text):
        violations.append(
            GuardrailViolation(
                category="personal_identifiers",
                trigger="ssn_format",
                description="Detected a pattern that matches a Social Security Number.",
            )
        )
    return violations


def detect_policy_violations(text: str) -> List[GuardrailViolation]:
    if not text:
        return []

    violations: List[GuardrailViolation] = []
    violations.extend(detect_keyword_violations(text))
    violations.extend(detect_pattern_violations(text))
    return violations


_PII_REASON_DESCRIPTIONS = {
    "payment_data": "Detected sensitive payment information.",
    "personal_identifiers": "Detected sensitive personal identifiers.",
}


def violations_from_pii_reasons(reasons: Iterable[str]) -> List[GuardrailViolation]:
    violations: List[GuardrailViolation] = []
    for reason in reasons:
        if not reason:
            continue
        category, _, trigger = reason.partition(":")
        category = category or "pii"
        trigger = trigger or category
        description = _PII_REASON_DESCRIPTIONS.get(category, "Detected sensitive information.")
        violations.append(GuardrailViolation(category=category, trigger=trigger, description=description))
    return violations
