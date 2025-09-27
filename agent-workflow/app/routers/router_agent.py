import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agents.base import RoutingDecision, RoutingRequest
from app.agents.router_agent import RouterAgent
from app.guardrails import get_guardrails_service
from app.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)
_guardrails_service = get_guardrails_service()


def get_router_agent() -> RouterAgent:
    return RouterAgent()


@router.post("/route", response_model=RoutingDecision)
def route_message(payload: RoutingRequest, agent: RouterAgent = Depends(get_router_agent)) -> RoutingDecision:
    pre_guardrails = _guardrails_service.preprocess_input(
        message=payload.message,
        user_id=None,
        metadata=None,
        origin="route",
    )
    processed_message = pre_guardrails.message

    logger.info(
        "route.start",
        extra={
            "guardrails_mode": settings.guardrails_mode,
            "guardrails_accents_stripped": pre_guardrails.flags.get("accents_stripped", False),
            "guardrails_injection_detected": pre_guardrails.flags.get("injection_detected", False),
            "guardrails_pii_masked": pre_guardrails.flags.get("pii_masked", False),
            "guardrails_pre_ms": pre_guardrails.latency_ms,
            "guardrails_masked_input_preview": pre_guardrails.masked_preview(),
        },
    )

    try:
        return agent.route_message(processed_message)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
