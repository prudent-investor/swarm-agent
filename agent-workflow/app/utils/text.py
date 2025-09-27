"""Utility helpers for text normalisation across the agent workflow."""

from __future__ import annotations

from typing import Final

_PORTUGUESE_ACCENT_TRANSLATION: Final[dict[int, str]] = {
    ord("á"): "a",
    ord("à"): "a",
    ord("â"): "a",
    ord("ã"): "a",
    ord("ä"): "a",
    ord("Á"): "A",
    ord("À"): "A",
    ord("Â"): "A",
    ord("Ã"): "A",
    ord("Ä"): "A",
    ord("é"): "e",
    ord("è"): "e",
    ord("ê"): "e",
    ord("ë"): "e",
    ord("É"): "E",
    ord("È"): "E",
    ord("Ê"): "E",
    ord("Ë"): "E",
    ord("í"): "i",
    ord("ì"): "i",
    ord("î"): "i",
    ord("ï"): "i",
    ord("Í"): "I",
    ord("Ì"): "I",
    ord("Î"): "I",
    ord("Ï"): "I",
    ord("ó"): "o",
    ord("ò"): "o",
    ord("ô"): "o",
    ord("õ"): "o",
    ord("ö"): "o",
    ord("Ó"): "O",
    ord("Ò"): "O",
    ord("Ô"): "O",
    ord("Õ"): "O",
    ord("Ö"): "O",
    ord("ú"): "u",
    ord("ù"): "u",
    ord("û"): "u",
    ord("ü"): "u",
    ord("Ú"): "U",
    ord("Ù"): "U",
    ord("Û"): "U",
    ord("Ü"): "U",
    ord("ç"): "c",
    ord("Ç"): "C",
    ord("ñ"): "n",
    ord("Ñ"): "N",
}


def strip_portuguese_accents(text: str) -> str:
    """Replace common Portuguese accented characters with their ASCII equivalent."""

    if not text:
        return text
    return text.translate(_PORTUGUESE_ACCENT_TRANSLATION)
