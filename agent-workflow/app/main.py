from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.logger import setup_logging
from app.observability.tracing import CorrelationContext
from app.routers.chat import router as chat_router
from app.routers.health import router as health_router
from app.routers.router_agent import router as router_agent_router
from app.routers.support_tickets import router as support_tickets_router
from app.settings import settings
from app.utils.text import strip_portuguese_accents


class AccentStrippingMiddleware(BaseHTTPMiddleware):
    """Ensure request bodies remain parseable when non-UTF8 accents are submitted.

    Some client environments (notably Windows terminals) may encode JSON payloads
    with latin-1 characters when users type Portuguese accents. FastAPI expects
    UTF-8 and will raise a parsing error otherwise. The middleware eagerly reads
    the request body, attempts to decode it as UTF-8, and falls back to latin-1
    while replacing accented characters with their ASCII counterparts. When a
    fallback occurs, we mark the request state so downstream consumers know the
    payload has already been normalised.
    """

    async def dispatch(self, request, call_next):  # type: ignore[override]
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if body:
                accents_stripped = False
                try:
                    # Try to decode as UTF-8 first. If it succeeds we leave the
                    # original payload untouched so other normalisers can run.
                    body.decode("utf-8")
                except UnicodeDecodeError:
                    decoded = body.decode("latin-1")
                    normalised = strip_portuguese_accents(decoded)
                    accents_stripped = normalised != decoded
                    body = normalised.encode("utf-8")
                if accents_stripped:
                    request.state.accents_stripped = True

                request._body = body  # type: ignore[attr-defined]
        return await call_next(request)


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title=settings.app_name, version=settings.app_version, docs_url="/docs")
    app.add_middleware(CorrelationContext)
    app.add_middleware(AccentStrippingMiddleware)
    allowed_origins = [origin.strip() for origin in settings.frontend_allowed_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(router_agent_router)
    app.include_router(chat_router)
    app.include_router(support_tickets_router)

    if settings.metrics_enabled:
        from app.routers.metrics import router as metrics_router

        app.include_router(metrics_router)

    if settings.readiness_enabled:
        from app.routers.readiness import router as readiness_router

        app.include_router(readiness_router)

    if settings.rag_admin_enabled:
        from app.routers.rag_admin import router as rag_admin_router

        app.include_router(rag_admin_router)

    if settings.rag_diagnostics_enabled:
        from app.routers.rag_diagnostics import router as rag_diag_router

        app.include_router(rag_diag_router)

    if settings.guardrails_diagnostics_enabled:
        from app.routers.guardrails import router as guardrails_router

        app.include_router(guardrails_router)

    return app


app = create_app()
