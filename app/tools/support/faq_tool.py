from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import List, Optional

from app.settings import settings

from .contracts import FAQItem, FAQQuery, FAQResult

logger = logging.getLogger(__name__)


class FAQTool:
    def __init__(self, *, dataset_path: Optional[Path] = None) -> None:
        self.dataset_path = dataset_path or Path("data") / "support" / "faq.json"
        self._items: List[FAQItem] = []
        self._load_dataset()

    def _load_dataset(self) -> None:
        try:
            payload = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("support.faq.dataset_missing", extra={"path": str(self.dataset_path)})
            payload = []
        except json.JSONDecodeError as exc:
            logger.error("support.faq.dataset_invalid", extra={"error": str(exc)})
            payload = []

        self._items = [
            FAQItem(
                id=item.get("id", ""),
                pergunta=item.get("pergunta", ""),
                resposta=item.get("resposta", ""),
                tags=[tag.lower() for tag in item.get("tags", [])],
                categoria=item.get("categoria", "outros"),
                atualizado_em=item.get("atualizado_em", ""),
            )
            for item in payload
        ]

    def reload(self) -> None:
        self._load_dataset()

    def search(self, query: FAQQuery) -> Optional[FAQResult]:
        if not self._items:
            return None

        message = _normalise(query.message)
        tokens = [token for token in message.split() if len(token) > 1]
        if not tokens:
            return None

        best_result: Optional[FAQResult] = None
        threshold = settings.support_faq_score_threshold

        for item in self._items:
            score = _score_item(item, tokens)
            if score < threshold:
                continue
            explanation = _build_explanation(item, tokens, score)
            result = FAQResult(item=item, score=round(score, 3), explanation=explanation)
            if not best_result or result.score > best_result.score:
                best_result = result

        return best_result


def _normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9çãõáéíóúâêîôûàèìòùñ ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _score_item(item: FAQItem, tokens: List[str]) -> float:
    if not item.pergunta or not item.resposta:
        return 0.0

    pergunta = _normalise(item.pergunta)
    resposta = _normalise(item.resposta)
    tags = item.tags

    total = 0.0
    for token in tokens:
        occurrences = pergunta.count(token) * 0.6 + resposta.count(token) * 0.4
        if occurrences:
            total += occurrences
        if token in tags:\n            total += 1.0

    total = min(total, len(tokens) * 2)
    if not total:
        return 0.0

    score = total / (len(tokens) * 2)
    score = max(0.0, min(score, 1.0))
    return score


def _build_explanation(item: FAQItem, tokens: List[str], score: float) -> str:
    matched_tokens = [token for token in tokens if token in _normalise(item.pergunta) or token in item.tags]
    return f"Tokens: {', '.join(matched_tokens)} | score={score:.2f}"



