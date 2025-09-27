from fastapi import APIRouter, HTTPException, Query

from app.guardrails import get_guardrails_service
from app.settings import settings

router = APIRouter()


@router.get("/guardrails/diagnostics")
def guardrails_diagnostics(query: str = Query(..., min_length=1, max_length=settings.guardrails_max_input_chars)) -> dict:
    if not settings.guardrails_diagnostics_enabled:
        raise HTTPException(status_code=404, detail="Diagnostico nao habilitado.")
    service = get_guardrails_service()
    return service.diagnostics(query)
