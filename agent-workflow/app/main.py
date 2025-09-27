from fastapi import FastAPI

from .routers.chat import router as chat_router
from .routers.health import router as health_router
from .routers.router_agent import router as router_agent_router
from .routers.support_tickets import router as support_tickets_router
from .settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, docs_url="/docs")
    app.include_router(health_router)
    app.include_router(router_agent_router)
    app.include_router(chat_router)
    app.include_router(support_tickets_router)

    if settings.rag_admin_enabled:
        from .routers.rag_admin import router as rag_admin_router

        app.include_router(rag_admin_router)

    if settings.rag_diagnostics_enabled:
        from .routers.rag_diagnostics import router as rag_diag_router

        app.include_router(rag_diag_router)

    if settings.guardrails_diagnostics_enabled:
        from .routers.guardrails import router as guardrails_router

        app.include_router(guardrails_router)

    return app


app = create_app()
