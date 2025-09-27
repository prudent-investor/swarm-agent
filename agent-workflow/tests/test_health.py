import asyncio

from httpx import AsyncClient

from app.main import app


async def _request_health():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.get("/health")
    return response


def test_health_endpoint():
    response = asyncio.run(_request_health())

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["status"], str)
    assert isinstance(payload["app"], str)
    assert isinstance(payload["version"], str)
    assert isinstance(payload["uptime_seconds"], (int, float))
