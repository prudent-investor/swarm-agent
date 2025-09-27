from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from app.settings import settings


@dataclass(frozen=True)
class InjectionPattern:
    value: str
    is_regex: bool = False

    def regex(self) -> re.Pattern[str]:
        if self.is_regex:
            return re.compile(self.value, re.IGNORECASE)
        return re.compile(re.escape(self.value), re.IGNORECASE)


_DEFAULT_PATTERNS: Tuple[InjectionPattern, ...] = (
    InjectionPattern("ignore previous instructions"),
    InjectionPattern("disregard previous instructions"),
    InjectionPattern("act as system"),
    InjectionPattern("you are now system"),
    InjectionPattern("developer mode"),
    InjectionPattern("sudo"),
    InjectionPattern("system prompt"),
    InjectionPattern("reveal password"),
    InjectionPattern("leak secrets"),
    InjectionPattern("override guardrails"),
    InjectionPattern(r"\bignore\b.*\binstruc\w*", True),
    InjectionPattern(r"\bignore\b.*\banter\w*", True),
    InjectionPattern(r"\bcomply\b.*\boverride\b", True),
    InjectionPattern(r"\bypass\b.*\bsecurity\b", True),

)


def _configured_patterns() -> Iterable[InjectionPattern]:
    configured = settings.guardrails_anti_injection_patterns or ""
    for raw in configured.split(";"):
        text = raw.strip()
        if text:
            yield InjectionPattern(text.lower())


def _patterns() -> List[InjectionPattern]:
    merged: List[InjectionPattern] = list(_DEFAULT_PATTERNS)
    merged.extend(_configured_patterns())
    unique: List[InjectionPattern] = []
    seen: set[str] = set()
    for pattern in merged:
        key = pattern.value.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(pattern)
    return unique


def cleanse_injection(text: str) -> Tuple[str, bool, List[str]]:
    if not text:
        return "", False, []

    detected: List[str] = []
    cleaned = text

    for pattern in _patterns():
        regex = pattern.regex()
        if regex.search(cleaned):
            detected.append(pattern.value)
            cleaned = regex.sub("", cleaned)

    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, bool(detected), detected
