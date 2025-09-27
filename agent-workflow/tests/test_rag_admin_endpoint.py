from fastapi.testclient import TestClient

from app import main
from app.rag.runner import RAGResult
from app.settings import settings


def test_rag_admin_endpoint_disabled(monkeypatch):
    monkeypatch.setattr(settings, "rag_admin_enabled", False)
    app_instance = main.create_app()
    client = TestClient(app_instance)

    response = client.post("/rag/reindex", json={"confirm": True})
    assert response.status_code == 404


def test_rag_admin_endpoint_requires_confirmation(monkeypatch):
    monkeypatch.setattr(settings, "rag_admin_enabled", True)
    app_instance = main.create_app()
    monkeypatch.setattr("app.routers.rag_admin.RAGRunner.run", lambda self: RAGResult(1, 1, 1, 0, 0, True))
    client = TestClient(app_instance)

    response = client.post("/rag/reindex", json={"confirm": False})
    assert response.status_code == 400


def test_rag_admin_endpoint_runs(monkeypatch):
    monkeypatch.setattr(settings, "rag_admin_enabled", True)
    app_instance = main.create_app()

    def fake_run(self):
        return RAGResult(processed_urls=2, raw_count=2, chunks_count=4, embedded_count=0, index_count=0, dry_run=True)

    monkeypatch.setattr("app.routers.rag_admin.RAGRunner.run", fake_run)
    client = TestClient(app_instance)

    response = client.post("/rag/reindex", json={"confirm": True, "dry_run": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["chunks_created"] == 4
