from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.services.rag import RetrievedChunk
from app.settings import settings


def test_rag_diagnostics_endpoint_disabled(monkeypatch):
    monkeypatch.setattr(settings, "rag_diagnostics_enabled", False)
    app_instance = main.create_app()
    client = TestClient(app_instance)

    response = client.post("/rag/diagnostics", json={"query": "maquininha"})

    assert response.status_code == 404


def test_rag_diagnostics_endpoint_enabled(monkeypatch):
    monkeypatch.setattr(settings, "rag_diagnostics_enabled", True)

    chunk = RetrievedChunk(
        id="a",
        url="https://www.infinitepay.io/maquininha",
        title="Maquininha",
        order=0,
        text="A maquininha InfinitePay possui taxas competitivas.",
        raw_score=0.9,
        content_hash="hash",
        ingest_timestamp=None,
        rank_score=0.9,
    )

    from app.routers import rag_diagnostics

    monkeypatch.setattr(rag_diagnostics, "_retriever", type("R", (), {"retrieve": lambda self, query, top_k=None: [chunk]})())
    monkeypatch.setattr(rag_diagnostics, "_reranker", type("RR", (), {"rerank": lambda self, query, chunks: list(chunks)})())
    monkeypatch.setattr(rag_diagnostics, "build_context", lambda chunks, max_chars: ("context", list(chunks)))
    monkeypatch.setattr(rag_diagnostics, "build_citations", lambda chunks, fallback_urls: [{"title": "Maquininha", "url": "https://www.infinitepay.io/maquininha", "source_type": "infinitepay"}])

    app_instance = main.create_app()
    client = TestClient(app_instance)

    response = client.post("/rag/diagnostics", json={"query": "maquininha"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"]
    assert payload["retrieved"]
