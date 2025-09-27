from __future__ import annotations

import re
from typing import List, Tuple

from app.settings import settings

EMAIL_RE = re.compile(r"([\w._%+-]+)@([\w.-]+)")
PHONE_RE = re.compile(r"\b\+?\d[\d\s\-]{7,}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _append_reason(reasons: List[str], category: str, trigger: str) -> None:
    reasons.append(f"{category}:{trigger}")


def mask_text(text: str) -> Tuple[str, bool, List[str]]:
    if not text or not settings.pii_masking_enabled:
        return text, False, []

    masked = text
    flagged = False
    reasons: List[str] = []

    if settings.pii_mask_email:
        if EMAIL_RE.search(masked):
            flagged = True
            masked = EMAIL_RE.sub(lambda m: _mask_email(m.group(1), m.group(2)), masked)
            _append_reason(reasons, "personal_identifiers", "email")

    if settings.pii_mask_phone:
        phone_matches = list(PHONE_RE.finditer(masked))
        phone_replacements = False
        for match in reversed(phone_matches):
            if _should_skip_phone_mask(masked, match):
                continue
            flagged = True
            phone_replacements = True
            masked = masked[: match.start()] + _mask_phone(match) + masked[match.end():]
        if phone_replacements:
            _append_reason(reasons, "personal_identifiers", "phone")

    card_matches = list(CARD_RE.finditer(masked))
    card_replacements = False
    for match in reversed(card_matches):
        if _should_skip_card_mask(masked, match):
            continue
        flagged = True
        card_replacements = True
        masked = masked[: match.start()] + _mask_card_number(match) + masked[match.end():]
    if card_replacements:
        _append_reason(reasons, "payment_data", "card_number")

    if SSN_RE.search(masked):
        flagged = True
        masked = SSN_RE.sub(_mask_ssn, masked)
        _append_reason(reasons, "personal_identifiers", "ssn")

    return masked, flagged, reasons


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

def _should_skip_phone_mask(text: str, match: re.Match[str]) -> bool:
    return _has_ticket_prefix(text, match)

def _should_skip_card_mask(text: str, match: re.Match[str]) -> bool:
    return _has_ticket_prefix(text, match)

def _has_ticket_prefix(text: str, match: re.Match[str]) -> bool:
    prefix = text[: match.start()]
    return bool(re.search(r"[A-Z]{3,}-$", prefix))

def _mask_card_number(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) <= 4:
        return "*" * len(digits)
    masked = "*" * (len(digits) - 4) + digits[-4:]
    groups = [masked[i : i + 4] for i in range(0, len(masked), 4)]
    return " ".join(groups)


def _mask_ssn(match: re.Match[str]) -> str:
    return "***-**-" + match.group(0)[7:]
