from fastapi import APIRouter

from ..settings import settings
from ..utils.runtime import runtime_state

router = APIRouter()


@router.get("/health")
def read_health():
    """Return application health status and runtime metadata."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "uptime_seconds": runtime_state.uptime_seconds(),
    }
