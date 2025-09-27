from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from app.schemas import ErrorResponse, TicketPublicResponse
from app.services.support_service import SupportService, get_support_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["support"])


@router.get(
    "/support/tickets/{ticket_id}",
    response_model=TicketPublicResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_ticket(
    ticket_id: str,
    correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-ID"),
    service: SupportService = Depends(get_support_service),
):
    corr_id = correlation_id or "support-ticket"
    logger.info(
        "support.ticket_lookup.start",
        extra={"correlation_id": corr_id, "ticket_id": ticket_id},
    )
    ticket = service.get_ticket_public(ticket_id)
    if not ticket:
        logger.info(
            "support.ticket_lookup.not_found",
            extra={"correlation_id": corr_id, "ticket_id": ticket_id},
        )
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(error="ticket_not_found", message="Ticket nao encontrado.").model_dump(),
        )
    logger.info(
        "support.ticket_lookup.success",
        extra={"correlation_id": corr_id, "ticket_id": ticket_id},
    )
    return TicketPublicResponse(**asdict(ticket))
