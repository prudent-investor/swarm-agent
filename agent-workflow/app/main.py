from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.observability.logger import setup_logging
from app.observability.tracing import CorrelationContext
from app.routers.chat import router as chat_router
from app.routers.health import router as health_router
from app.routers.router_agent import router as router_agent_router
from app.routers.support_tickets import router as support_tickets_router
from app.settings import settings


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title=settings.app_name, version=settings.app_version, docs_url="/docs")
    app.add_middleware(CorrelationContext)
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
