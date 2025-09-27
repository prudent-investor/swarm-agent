from __future__ import annotations

import httpx

if not getattr(httpx.AsyncClient, "_swarm_patched", False):  # pragma: no cover - import side effect
    _original_init = httpx.AsyncClient.__init__

    def _patched_async_client_init(self, *args, app=None, transport=None, **kwargs):
        if app is not None and transport is None:
            transport = httpx.ASGITransport(app=app)
            app = None
        return _original_init(self, *args, app=app, transport=transport, **kwargs)

    httpx.AsyncClient.__init__ = _patched_async_client_init  # type: ignore[assignment]
    httpx.AsyncClient._swarm_patched = True  # type: ignore[attr-defined]
