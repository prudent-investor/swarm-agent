from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional

from app.settings import settings
from app.tools.support import FAQTool, TicketTool
from app.tools.support.contracts import FAQQuery, FAQResult, Ticket, TicketCreateRequest, TicketPublicView
from app.agents.support_policies import PolicyDecision, decide

logger = logging.getLogger(__name__)


@dataclass
class SupportMetrics:
    total_requests: int = 0
    faq_hits: int = 0
    tickets_created: int = 0
    escalations: int = 0
    total_latency_ms: float = 0.0

    def add_latency(self, value: float) -> None:
        self.total_latency_ms += value

    @property
    def average_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.total_latency_ms / self.total_requests, 2)


def mask_pii(value: Optional[str]) -> Optional[str]:
    if not value or not settings.support_pii_masking_enabled:
        return value
    masked = re.sub(r"([\w._%+-]+)@([\w.-]+)", r"***@\2", value)
    masked = re.sub(r"\b\d{5}\d+\b", "***", masked)
    return masked


class SupportService:
    def __init__(
        self,
        faq_tool: Optional[FAQTool] = None,
        ticket_tool: Optional[TicketTool] = None,
    ) -> None:
        self._faq_tool = faq_tool or FAQTool()
        self._ticket_tool = ticket_tool or TicketTool()
        self.metrics = SupportMetrics()

    def handle_support(self, message: str, user_id: Optional[str], correlation_id: str) -> Dict[str, object]:
        start = time.perf_counter()
        self.metrics.total_requests += 1

        faq_result = self._faq_tool.search(FAQQuery(message)) if settings.support_faq_enabled else None
        if faq_result:
            self.metrics.faq_hits += 1
            latency = (time.perf_counter() - start) * 1000
            self.metrics.add_latency(latency)
            logger.info(
                "support.faq_hit",
                extra={
                    "correlation_id": correlation_id,
                    "faq_id": faq_result.item.id,
                    "score": faq_result.score,
                },
            )
            return {
                "faq_result": faq_result,
                "ticket": None,
                "policy": None,
                "latency_ms": round(latency, 2),
            }

        policy = decide(message)
        create_request = TicketCreateRequest(
            summary=_build_summary(message),
            description=message,
            user_id=user_id,
            category=policy.category,
            priority=policy.priority,
            escalation=policy.escalation,
        )
        ticket = self._ticket_tool.create(create_request)
        self.metrics.tickets_created += 1
        if ticket.escalation:
            self.metrics.escalations += 1

        latency = (time.perf_counter() - start) * 1000
        self.metrics.add_latency(latency)
        logger.info(
            "support.ticket_created",
            extra={
                "correlation_id": correlation_id,
                "ticket_id": ticket.id,
                "priority": ticket.priority,
                "category": ticket.category,
                "escalation": ticket.escalation,
            },
        )
        return {
            "faq_result": None,
            "ticket": ticket,
            "policy": policy,
            "latency_ms": round(latency, 2),
        }

    def get_ticket_public(self, ticket_id: str) -> Optional[TicketPublicView]:
        ticket = self._ticket_tool.get(ticket_id)
        if not ticket:
            return None
        return TicketPublicView(
            id=ticket.id,
            status=ticket.status,
            created_at=ticket.created_at.isoformat(),
            updated_at=ticket.updated_at.isoformat(),
            priority=ticket.priority,
            category=ticket.category,
            summary=ticket.summary,
            user_ref=mask_pii(ticket.user_id),
        )


def _build_summary(message: str) -> str:
    summary = message.split(".")[0]
    if len(summary) > 120:
        summary = summary[:117] + "..."
    return summary


_SUPPORT_SERVICE: Optional[SupportService] = None


def get_support_service() -> SupportService:
    global _SUPPORT_SERVICE
    if _SUPPORT_SERVICE is None:
        _SUPPORT_SERVICE = SupportService()
    return _SUPPORT_SERVICE
