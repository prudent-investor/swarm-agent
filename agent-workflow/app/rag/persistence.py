from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .loader import RawDocument
from .splitter import Chunk


@dataclass
class Manifest:
    run_id: str
    timestamp: str
    total_urls: int
    processed_documents: int
    chunks_created: int
    embedded_chunks: int
    index_items: int
    dry_run: bool


def save_raw_documents(documents: Iterable[RawDocument], *, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp()
    path = directory / f"raw_{timestamp}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for doc in documents:
            fh.write(
                json.dumps(
                    {
                        "url": doc.url,
                        "status": doc.status,
                        "title": doc.title,
                        "html": doc.html,
                        "captured_at": doc.captured_at,
                        "content_hash": doc.content_hash,
                    },
                    ensure_ascii=False,
                )
            )
            fh.write("\n")
    return path


def save_chunks(chunks: Iterable[Chunk], *, directory: Path, stage: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp()
    path = directory / f"chunks_{stage}_{timestamp}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(
                json.dumps(
                    {
                        "id": chunk.id,
                        "url": chunk.url,
                        "title": chunk.title,
                        "order": chunk.order,
                        "text": chunk.text,
                        "embedding": chunk.embedding,
                        "content_hash": chunk.content_hash,
                    },
                    ensure_ascii=False,
                )
            )
            fh.write("\n")
    return path


def save_manifest(manifest: Manifest, *, index_dir: Path) -> Path:
    index_dir.mkdir(parents=True, exist_ok=True)
    path = index_dir / f"manifest_{manifest.run_id}.json"
    path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
