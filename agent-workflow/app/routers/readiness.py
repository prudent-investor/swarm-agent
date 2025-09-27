from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.observability.readiness import get_readiness_checker
from app.settings import settings


router = APIRouter()


@router.get("/readiness")
def readiness_endpoint() -> dict:
    if not settings.readiness_enabled:
        raise HTTPException(status_code=404, detail="Readiness disabled")

    checker = get_readiness_checker()
    status = checker.evaluate()
    response = {
        "status": "ready" if status.ready else "unready",
        "checks": {
            name: {"ok": ok, "detail": detail}
            for name, (ok, detail) in status.checks.items()
        },
    }
    if not status.ready:
        return JSONResponse(status_code=503, content=response)
    return response
