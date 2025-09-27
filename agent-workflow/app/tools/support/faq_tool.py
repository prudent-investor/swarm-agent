from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import List, Optional

from app.settings import settings

from .contracts import FAQItem, FAQQuery, FAQResult

logger = logging.getLogger(__name__)


class FAQTool:
    def __init__(self, *, dataset_path: Optional[Path] = None) -> None:
        self._dataset_path = dataset_path or Path("data") / "support" / "faq.json"
        self._items: List[FAQItem] = []
        self._load_dataset()

    def _load_dataset(self) -> None:
        try:
            raw = self._dataset_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning(
                "support.faq.dataset_missing",
                extra={"path": str(self._dataset_path)},
            )
            self._items = []
            return
        except OSError as exc:
            logger.error(
                "support.faq.dataset_unreadable",
                extra={"path": str(self._dataset_path), "error": str(exc)},
            )
            self._items = []
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(
                "support.faq.dataset_invalid",
                extra={"path": str(self._dataset_path), "error": str(exc)},
            )
            self._items = []
            return

        items: List[FAQItem] = []
        for entry in payload:
            try:
                item = FAQItem(
                    id=str(entry.get("id", "")),
                    pergunta=str(entry.get("pergunta", "")),
                    resposta=str(entry.get("resposta", "")),
                    tags=[str(tag).strip().lower() for tag in entry.get("tags", []) if str(tag).strip()],
                    categoria=str(entry.get("categoria", "outros")),
                    atualizado_em=str(entry.get("atualizado_em", "")),
                )
            except Exception as exc:  # pragma: no cover - defensive guard to avoid crash on dataset issues
                logger.warning(
                    "support.faq.dataset_item_invalid",
                    extra={"path": str(self._dataset_path), "error": str(exc)},
                )
                continue
            items.append(item)
        self._items = items

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
            if best_result is None or result.score > best_result.score:
                best_result = result

        return best_result


_WORD_RE = re.compile(r"[^a-z0-9 ]+")


def _normalise(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _WORD_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _score_item(item: FAQItem, tokens: List[str]) -> float:
    pergunta = _normalise(item.pergunta)
    resposta = _normalise(item.resposta)
    tags = item.tags
    if not pergunta and not resposta:
        return 0.0

    total = 0.0
    matched_tokens = 0
    for token in tokens:
        token_matched = False
        occurrences = pergunta.count(token) * 0.6 + resposta.count(token) * 0.4
        if occurrences:
            total += occurrences
            token_matched = True
        if token in tags:
            total += 1.0
            token_matched = True
        if token_matched:
            matched_tokens += 1

    if total <= 0:
        return 0.0

    max_candidates = [len(tokens), matched_tokens if matched_tokens else 1]
    max_score = max(max_candidates) * 1.5
    total = min(total, max_score)
    return max(0.0, min(total / max_score, 1.0))


def _build_explanation(item: FAQItem, tokens: List[str], score: float) -> str:
    pergunta = _normalise(item.pergunta)
    matched_tokens = [token for token in tokens if token in pergunta or token in item.tags]
    return f"tokens={','.join(matched_tokens)} score={score:.2f}"

