from fastapi import APIRouter, Response

from app.observability.metrics import format_prometheus_metrics
from app.settings import settings


router = APIRouter()


@router.get("/metrics", response_class=Response)
def metrics_endpoint() -> Response:
    if not settings.metrics_enabled:
        return Response(status_code=404)
    payload = format_prometheus_metrics()
    return Response(content=payload, media_type="text/plain; version=0.0.4")
