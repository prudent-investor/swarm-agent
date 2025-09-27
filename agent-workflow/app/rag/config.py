from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

from app.settings import settings


@dataclass(frozen=True)
class RAGPaths:
    base: Path
    sources_dir: Path
    raw_dir: Path
    chunks_dir: Path
    index_dir: Path
    seed_file: Path
    whitelist_file: Path

    def ensure(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class RAGConfig:
    paths: RAGPaths
    max_pages: int
    max_depth: int
    request_timeout: float
    request_interval: float
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    dry_run: bool = False


DEFAULT_DATA_BASE = Path("data") / "rag"
DEFAULT_SEED_FILE = DEFAULT_DATA_BASE / "sources" / "seed_urls.txt"
DEFAULT_WHITELIST_FILE = DEFAULT_DATA_BASE / "sources" / "whitelist.txt"


def create_paths(base: Path = DEFAULT_DATA_BASE) -> RAGPaths:
    return RAGPaths(
        base=base,
        sources_dir=base / "sources",
        raw_dir=base / "raw",
        chunks_dir=base / "chunks",
        index_dir=base / "index",
        seed_file=base / "sources" / "seed_urls.txt",
        whitelist_file=base / "sources" / "whitelist.txt",
    )


def create_config(*, dry_run: bool = False, base: Path | None = None) -> RAGConfig:
    paths = create_paths(base or DEFAULT_DATA_BASE)
    return RAGConfig(
        paths=paths,
        max_pages=settings.rag_max_pages,
        max_depth=settings.rag_max_depth,
        request_timeout=settings.rag_request_timeout,
        request_interval=settings.rag_request_interval,
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        embedding_model=settings.openai_embedding_model,
        dry_run=dry_run,
    )


def load_seed_urls(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]


def load_whitelist(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    return {line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")}
