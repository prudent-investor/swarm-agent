from __future__ import annotations

import re
import unicodedata
from typing import Tuple

from app.settings import settings
from app.utils.text import strip_portuguese_accents

_REMOVABLE_PATTERN = re.compile(r"[\s]{2,}")


def _decode_symbol_token(token: str) -> str:
    try:
        return bytes(token, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return token


def _strip_symbols(text: str) -> str:
    raw = settings.guardrails_normalize_strip_symbols or ""
    if not raw:
        return text
    translation: dict[int, str] = {}
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        decoded = _decode_symbol_token(token)
        for char in decoded:
            translation[ord(char)] = " "
    return text.translate(translation) if translation else text


def normalise_text(text: str) -> Tuple[str, bool]:
    if text is None:
        return "", False

    original = text
    normalised = text

    if settings.guardrails_normalize_remove_accents:
        normalised = strip_portuguese_accents(normalised)
        normalised = unicodedata.normalize("NFD", normalised)
        normalised = "".join(ch for ch in normalised if unicodedata.category(ch) != "Mn")
        normalised = unicodedata.normalize("NFC", normalised)

    normalised = _strip_symbols(normalised)
    normalised = _REMOVABLE_PATTERN.sub(" ", normalised)
    normalised = normalised.strip()

    changed = normalised != original
    return normalised, changed
