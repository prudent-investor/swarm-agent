from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .retriever import RetrievedChunk

OFFICIAL_URLS = {
    "https://www.infinitepay.io",
    "https://www.infinitepay.io/maquininha",
    "https://www.infinitepay.io/maquininha-celular",
    "https://www.infinitepay.io/tap-to-pay",
    "https://www.infinitepay.io/pdv",
    "https://www.infinitepay.io/receba-na-hora",
    "https://www.infinitepay.io/gestao-de-cobranca-2",
    "https://www.infinitepay.io/gestao-de-cobranca",
    "https://www.infinitepay.io/link-de-pagamento",
    "https://www.infinitepay.io/loja-online",
    "https://www.infinitepay.io/boleto",
    "https://www.infinitepay.io/conta-digital",
    "https://www.infinitepay.io/conta-pj",
    "https://www.infinitepay.io/pix",
    "https://www.infinitepay.io/pix-parcelado",
    "https://www.infinitepay.io/emprestimo",
    "https://www.infinitepay.io/cartao",
    "https://www.infinitepay.io/rendimento",
}


@dataclass
class Citation:
    title: str
    url: str
    source_type: str


def build_citations(
    chunks: Iterable[RetrievedChunk],
    *,
    fallback_urls: Sequence[str],
    external_sources: Sequence[Citation] | None = None,
) -> List[dict]:
    citations: List[Citation] = []
    seen_urls: set[str] = set()

    for chunk in chunks:
        url = chunk.url or "https://www.infinitepay.io"
        url = _canonical_url(url)
        if url in seen_urls:
            continue
        source_type = "infinitepay" if _is_official(url) else "external"
        title = chunk.title or _title_from_url(url)
        citations.append(Citation(title=title, url=url, source_type=source_type))
        seen_urls.add(url)

    if external_sources:
        for citation in external_sources:
            if citation.url in seen_urls:
                continue
            citations.append(citation)
            seen_urls.add(citation.url)

    if not citations:
        for url in fallback_urls:
            canon = _canonical_url(url)
            if canon in seen_urls:
                continue
            citations.append(Citation(title=_title_from_url(canon), url=canon, source_type="infinitepay"))
            seen_urls.add(canon)

    return [citation.__dict__ for citation in citations]


def _canonical_url(url: str) -> str:
    if not url:
        return "https://www.infinitepay.io"
    url = url.strip()
    url = re.sub(r"[?#].*", "", url)
    if url.endswith("/") and len(url) > len("https://") + 1:
        url = url.rstrip("/")
    return url


def _title_from_url(url: str) -> str:
    path = url.split("//", 1)[-1]
    if not path:
        return "InfinitePay"
    parts = path.split("/")
    if len(parts) > 1 and parts[1]:
        return parts[1].replace("-", " ").title()
    return "InfinitePay"


def _is_official(url: str) -> bool:
    return any(url.startswith(official) for official in OFFICIAL_URLS)
