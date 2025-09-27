from app.rag.cleaner import CleanDocument
from app.rag.splitter import split_document


def test_splitter_creates_overlapping_chunks():
    text = " ".join([f"sentenca{i}" for i in range(1, 21)])
    doc = CleanDocument(url="https://example.com", title="Exemplo", text=text, content_hash="hash123")

    chunks = split_document(doc, chunk_size=30, overlap=10)

    assert len(chunks) >= 2
    assert chunks[0].text.startswith("sentenca1")
    assert chunks[0].id.endswith("-0")
    assert chunks[1].id.endswith("-1")
    assert chunks[1].text.split()[0] == chunks[0].text.split()[-1]
