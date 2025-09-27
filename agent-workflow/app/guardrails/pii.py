from __future__ import annotations

import re
from typing import Tuple

from app.settings import settings

EMAIL_RE = re.compile(r"([\w._%+-]+)@([\w.-]+)")
PHONE_RE = re.compile(r"\b\+?\d[\d\s\-]{7,}\b")


def mask_text(text: str) -> Tuple[str, bool]:
    if not text or not settings.pii_masking_enabled:
        return text, False

    masked = text
    flagged = False

    if settings.pii_mask_email:
        if EMAIL_RE.search(masked):
            flagged = True
            masked = EMAIL_RE.sub(lambda m: _mask_email(m.group(1), m.group(2)), masked)

    if settings.pii_mask_phone:
        if PHONE_RE.search(masked):
            flagged = True
            masked = PHONE_RE.sub(_mask_phone, masked)

    return masked, flagged


def _mask_email(local: str, domain: str) -> str:
    visible = local[:2] if len(local) > 2 else "*"
    return f"{visible}{'*' * max(1, len(local) - len(visible))}@{domain}"


def _mask_phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) <= 4:
        return "*" * len(digits)
    prefix = "*" * (len(digits) - 2)
    suffix = digits[-2:]
    return f"{prefix}{suffix}"
