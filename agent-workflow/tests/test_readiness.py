from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import readiness
from app.settings import settings


@pytest.fixture(autouse=True)
def reset_readiness_checker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(readiness, "_checker", None)


def _prepare_index() -> Path:
    index_dir = Path("data") / "rag" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    index_file = index_dir / "index_test.jsonl"
    index_file.write_text("{}\n", encoding="utf-8")
    return index_file


def test_readiness_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "key-123")
    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "readiness_cpu_threshold", 95)
    monkeypatch.setattr(settings, "readiness_memory_threshold_mb", 2048)
    index_file = _prepare_index()

    with TestClient(app) as client:
        response = client.get("/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    index_file.unlink(missing_ok=True)


def test_readiness_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "rag_enabled", True)
    index_file = _prepare_index()

    with TestClient(app) as client:
        response = client.get("/readiness")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unready"
    assert payload["checks"]["openai_api_key"]["ok"] is False
    index_file.unlink(missing_ok=True)


def test_readiness_resource_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "key-123")
    monkeypatch.setattr(settings, "rag_enabled", True)
    index_file = _prepare_index()

    monkeypatch.setattr(readiness, "_cpu_usage_ok", lambda limit: (False, "cpu_usage=95.0"))
    monkeypatch.setattr(readiness, "_memory_usage_ok", lambda limit: (False, "memory_used_mb=2048.0"))

    with TestClient(app) as client:
        response = client.get("/readiness")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unready"
    assert payload["checks"]["system_resources"]["ok"] is False
    index_file.unlink(missing_ok=True)
