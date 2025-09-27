from pathlib import Path

from app.rag.cleaner import CleanDocument
from app.rag.config import create_config
from app.rag.loader import RawDocument
from app.rag.runner import RAGRunner
from app.rag.splitter import Chunk


def test_rag_runner_dry_run(tmp_path: Path) -> None:
    base = tmp_path / "rag"
    config = create_config(dry_run=True, base=base)

    raw_doc = RawDocument(
        url="https://example.com",
        status=200,
        title="Example",
        html="<article><p>Primeiro paragrafo.</p><p>Segundo paragrafo.</p></article>",
        captured_at="2024-01-01T00:00:00Z",
        content_hash="abc123",
    )

    clean_doc = CleanDocument(url=raw_doc.url, title=raw_doc.title, text="Primeiro paragrafo. Segundo paragrafo.", content_hash=raw_doc.content_hash)
    chunk = Chunk(id="abc123-0", url=raw_doc.url, title=raw_doc.title, order=0, text="Primeiro paragrafo.", content_hash=raw_doc.content_hash)

    runner = RAGRunner(
        config,
        loader_fn=lambda cfg: [raw_doc],
        cleaner_fn=lambda doc: clean_doc,
        splitter_fn=lambda doc: [chunk],
    )

    result = runner.run()

    assert result.dry_run is True
    assert result.raw_count == 1
    assert result.chunks_count == 1
    raw_files = list((base / "raw").glob("*.jsonl"))
    chunk_files = list((base / "chunks").glob("chunks_clean_*.jsonl"))
    manifest_files = list((base / "index").glob("manifest_*.json"))
    assert raw_files and chunk_files and manifest_files
