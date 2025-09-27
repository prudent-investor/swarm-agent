import json
from pathlib import Path

from app.rag.loader import RawDocument
from app.rag.persistence import Manifest, save_chunks, save_manifest, save_raw_documents
from app.rag.splitter import Chunk


def test_persistence_roundtrip(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    chunks_dir = tmp_path / "chunks"
    index_dir = tmp_path / "index"

    raw_doc = RawDocument(
        url="https://example.com",
        status=200,
        title="Example",
        html="<html><body>Example</body></html>",
        captured_at="2024-01-01T00:00:00Z",
        content_hash="abc123",
    )

    raw_path = save_raw_documents([raw_doc], directory=raw_dir)
    saved_raw = raw_path.read_text(encoding="utf-8").strip()
    assert "https://example.com" in saved_raw

    chunk = Chunk(
        id="abc123-0",
        url="https://example.com",
        title="Example",
        order=0,
        text="Example text chunk",
        content_hash="abc123",
    )
    chunks_path = save_chunks([chunk], directory=chunks_dir, stage="test")
    saved_chunk = json.loads(chunks_path.read_text(encoding="utf-8").splitlines()[0])
    assert saved_chunk["id"] == "abc123-0"

    manifest = Manifest(
        run_id="run123",
        timestamp="2024-01-01T00:00:00Z",
        total_urls=1,
        processed_documents=1,
        chunks_created=1,
        embedded_chunks=0,
        index_items=0,
        dry_run=True,
    )
    manifest_path = save_manifest(manifest, index_dir=index_dir)
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["run_id"] == "run123"
