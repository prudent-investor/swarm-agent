from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable, List

from .cleaner import CleanDocument, clean_document
from .config import RAGConfig, create_config, load_seed_urls, load_whitelist
from .embedder import ChunkEmbedder
from .indexer import build_index
from .loader import RawDocument, load_documents
from .persistence import Manifest, save_chunks, save_manifest, save_raw_documents
from .splitter import Chunk, split_document

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    processed_urls: int
    raw_count: int
    chunks_count: int
    embedded_count: int
    index_count: int
    dry_run: bool


class RAGRunner:
    def __init__(
        self,
        config: RAGConfig,
        *,
        loader_fn: Callable[[RAGConfig], List[RawDocument]] | None = None,
        cleaner_fn: Callable[[RawDocument], CleanDocument] = clean_document,
        splitter_fn: Callable[[CleanDocument], List[Chunk]] | None = None,
        embedder: ChunkEmbedder | None = None,
    ) -> None:
        self.config = config
        self.loader_fn = loader_fn or (lambda cfg: load_documents(cfg))
        self.cleaner_fn = cleaner_fn
        self.splitter_fn = splitter_fn
        self.embedder = embedder

    def run(self) -> RAGResult:
        start_time = time.perf_counter()
        self.config.paths.ensure()

        seed_urls = load_seed_urls(self.config.paths.seed_file)
        whitelist = load_whitelist(self.config.paths.whitelist_file)
        logger.info(
            "rag.runner.start",
            extra={
                "dry_run": self.config.dry_run,
                "seed_count": len(seed_urls),
                "whitelist": len(whitelist),
            },
        )

        raw_documents = self.loader_fn(self.config)
        raw_path = save_raw_documents(raw_documents, directory=self.config.paths.raw_dir)
        logger.info("rag.runner.raw_saved", extra={"path": str(raw_path), "count": len(raw_documents)})

        clean_documents = [self.cleaner_fn(doc) for doc in raw_documents]
        splitter = self.splitter_fn or (lambda doc: split_document(doc, chunk_size=self.config.chunk_size, overlap=self.config.chunk_overlap))

        chunks: List[Chunk] = []
        for clean_doc in clean_documents:
            chunks.extend(splitter(clean_doc))

        pre_embed_path = save_chunks(chunks, directory=self.config.paths.chunks_dir, stage="clean")
        logger.info("rag.runner.chunks_created", extra={"count": len(chunks), "path": str(pre_embed_path)})

        embedded_count = 0
        index_count = 0
        if not self.config.dry_run and chunks:
            embedder = self.embedder or ChunkEmbedder(model=self.config.embedding_model)
            chunks = embedder.embed(chunks)
            embedded_count = sum(1 for chunk in chunks if chunk.embedding)
            post_embed_path = save_chunks(chunks, directory=self.config.paths.chunks_dir, stage="embedded")
            logger.info("rag.runner.chunks_embedded", extra={"count": embedded_count, "path": str(post_embed_path)})

            artifact = build_index(chunks, index_dir=self.config.paths.index_dir)
            index_count = artifact.count
            logger.info("rag.runner.index_created", extra={"path": str(artifact.path), "count": artifact.count})
        else:
            logger.info("rag.runner.embed_skip", extra={"dry_run": self.config.dry_run})

        run_id = uuid.uuid4().hex
        manifest = Manifest(
            run_id=run_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            total_urls=len(seed_urls),
            processed_documents=len(raw_documents),
            chunks_created=len(chunks),
            embedded_chunks=embedded_count,
            index_items=index_count,
            dry_run=self.config.dry_run,
        )
        manifest_path = save_manifest(manifest, index_dir=self.config.paths.index_dir)
        logger.info(
            "rag.runner.completed",
            extra={
                "manifest": str(manifest_path),
                "duration": round(time.perf_counter() - start_time, 2),
            },
        )

        return RAGResult(
            processed_urls=len(seed_urls),
            raw_count=len(raw_documents),
            chunks_count=len(chunks),
            embedded_count=embedded_count,
            index_count=index_count,
            dry_run=self.config.dry_run,
        )


def run_pipeline(*, dry_run: bool = False) -> RAGResult:
    config = create_config(dry_run=dry_run)
    runner = RAGRunner(config)
    return runner.run()
