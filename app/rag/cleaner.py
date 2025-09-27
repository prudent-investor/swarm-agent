from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .loader import RawDocument

logger = logging.getLogger(__name__)


@dataclass
class CleanDocument:
    url: str
    title: str | None
    text: str
    content_hash: str


def clean_document(raw: RawDocument) -> CleanDocument:
    if not raw.html:
        logger.warning("rag.cleaner.empty_html", extra={"url": raw.url})
        return CleanDocument(url=raw.url, title=raw.title, text="", content_hash=raw.content_hash)

    soup = BeautifulSoup(raw.html, "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header", "aside"]):
        tag.decompose()

    main = soup.find("article") or soup.find("main") or soup.body
    text = main.get_text(separator="\n") if main else soup.get_text(separator="\n")
    text = _normalise(text)

    title = raw.title or (soup.title.string.strip() if soup.title and soup.title.string else None)

    return CleanDocument(url=raw.url, title=title, text=text, content_hash=raw.content_hash)


def _normalise(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
