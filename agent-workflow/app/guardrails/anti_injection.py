from __future__ import annotations

import re
from typing import List, Tuple

from app.settings import settings

_DEFAULT_PATTERNS = [
    "ignore previous instructions",
    "act as system",
    "you are now system",
    "developer mode",
    "sudo",
    "system prompt",
]


def _patterns() -> List[str]:
    configured = settings.guardrails_anti_injection_patterns or ""
    custom = [pattern.strip().lower() for pattern in configured.split(";") if pattern.strip()]
    merged = [pattern.lower() for pattern in _DEFAULT_PATTERNS]
    merged.extend(custom)
    # Preserve order while removing duplicates
    return list(dict.fromkeys(merged))


def cleanse_injection(text: str) -> Tuple[str, bool, List[str]]:
    if not text:
        return "", False, []
    detected: List[str] = []
    cleaned = text
    for pattern in _patterns():
        if not pattern:
            continue
        regex = re.compile(re.escape(pattern), re.IGNORECASE)
        if regex.search(cleaned):
            detected.append(pattern)
            cleaned = regex.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, bool(detected), detected