from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.settings import settings

from .metrics import get_metrics_registry


correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationContext(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        header_name = settings.correlation_id_header
        inbound_id = request.headers.get(header_name)
        correlation_id = inbound_id or str(uuid4())
        token = correlation_id_var.set(correlation_id)
        request.state.correlation_id = correlation_id
        start = time.perf_counter()

        try:
            response = await call_next(request)
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            if request.url.path == "/chat" and request.method.upper() == "POST":
                get_metrics_registry().observe_latency(latency_ms, correlation_id=correlation_id)
            correlation_id_var.reset(token)

        response.headers[header_name] = correlation_id
        return response


def get_correlation_id(default: str | None = None) -> str | None:
    return correlation_id_var.get() or default


def set_correlation_id(value: str) -> None:
    correlation_id_var.set(value)
