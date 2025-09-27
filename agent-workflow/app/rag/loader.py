from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Set
from urllib.parse import urlparse

import httpx

from .config import RAGConfig, load_seed_urls, load_whitelist

logger = logging.getLogger(__name__)


@dataclass
class RawDocument:
    url: str
    status: int
    title: str | None
    html: str
    captured_at: str
    content_hash: str


def _default_fetch(url: str, timeout: float) -> httpx.Response:
    headers = {"User-Agent": "AgentWorkflowRAG/1.0"}
    with httpx.Client(timeout=timeout) as client:
        return client.get(url, headers=headers)


def load_documents(
    config: RAGConfig,
    *,
    fetcher: Callable[[str, float], httpx.Response] = _default_fetch,
) -> List[RawDocument]:
    if config.dry_run:
        logger.info("rag.loader.skip", extra={"reason": "dry_run"})
        return []

    seeds = load_seed_urls(config.paths.seed_file)
    whitelist = load_whitelist(config.paths.whitelist_file)

    documents: List[RawDocument] = []
    seen_hashes: Set[str] = set()
    processed = 0

    for url in seeds:
        if processed >= config.max_pages:
            break

        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain not in whitelist and ("www." + domain) not in whitelist:
            logger.warning("rag.loader.skip_domain", extra={"url": url, "domain": domain})
            continue

        try:
            response = fetcher(url, config.request_timeout)
            status = response.status_code
            html = response.text if status == 200 else ""
        except Exception as exc:  # pragma: no cover
            logger.error("rag.loader.error", extra={"url": url, "error": str(exc)})
            continue

        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            logger.info("rag.loader.duplicate", extra={"url": url})
            continue

        title = _extract_title(html)
        captured_at = datetime.now(timezone.utc).isoformat()
        documents.append(
            RawDocument(
                url=url,
                status=status,
                title=title,
                html=html,
                captured_at=captured_at,
                content_hash=content_hash,
            )
        )
        seen_hashes.add(content_hash)
        processed += 1
        time.sleep(config.request_interval)

    logger.info("rag.loader.completed", extra={"documents": len(documents)})
    return documents


def _extract_title(html: str) -> str | None:
    lower = html.lower()
    start = lower.find("<title>")
    end = lower.find("</title>")
    if start != -1 and end != -1 and end > start:
        return html[start + 7 : end].strip()
    return None
