from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .splitter import Chunk


class IndexArtifact:
    def __init__(self, path: Path, count: int) -> None:
        self.path = path
        self.count = count


def build_index(chunks: Iterable[Chunk], *, index_dir: Path) -> IndexArtifact:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    index_path = index_dir / f"index_{timestamp}.jsonl"
    index_dir.mkdir(parents=True, exist_ok=True)

    serialised: List[str] = []
    for chunk in chunks:
        serialised.append(
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

    index_path.write_text("\n".join(serialised), encoding="utf-8")
    return IndexArtifact(path=index_path, count=len(serialised))
