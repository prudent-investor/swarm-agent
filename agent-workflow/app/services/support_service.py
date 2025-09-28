from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, Optional

from app.agents.support_policies import PolicyDecision, decide
from app.settings import settings
from app.tools.support import (
    AccountStatusTool,
    FAQQuery,
    FAQResult,
    FAQTool,
    Ticket,
    TicketCreateRequest,
    TicketPublicView,
    TicketTool,
    UserProfile,
    UserProfileTool,
)

logger = logging.getLogger(__name__)


@dataclass
class SupportMetrics:
    total_requests: int = 0
    faq_hits: int = 0
    tickets_created: int = 0
    escalations: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    max_samples: int = 2000

    def add_latency(self, value: float) -> None:
        self.latencies_ms.append(value)
        if len(self.latencies_ms) > self.max_samples:
            self.latencies_ms.pop(0)

    @property
    def average_latency_ms(self) -> float:
        return round(mean(self.latencies_ms), 2) if self.latencies_ms else 0.0

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_values = sorted(self.latencies_ms)
        index = max(0, int(len(sorted_values) * 0.95) - 1)
        return round(sorted_values[index], 2)


def _mask_pii(value: Optional[str]) -> Optional[str]:
    if not value or not settings.support_pii_masking_enabled:
        return value
    masked = re.sub(r"([\w._%+-]+)@([\w.-]+)", r"***@\2", value)
    masked = re.sub(r"\b(\d{2})\d{3}(\d{2,})\b", r"\1***\2", masked)
    masked = re.sub(r"\b\d{5,}\b", "***", masked)
    return masked


class SupportService:
    def __init__(
        self,
        *,
        faq_tool: Optional[FAQTool] = None,
        ticket_tool: Optional[TicketTool] = None,
        profile_tool: Optional[UserProfileTool] = None,
        account_status_tool: Optional[AccountStatusTool] = None,
    ) -> None:
        self._faq_tool = faq_tool or FAQTool()
        self._ticket_tool = ticket_tool or TicketTool()
        self._profile_tool = profile_tool or UserProfileTool()
        self._account_tool = account_status_tool or AccountStatusTool()
        self.metrics = SupportMetrics()

    def handle_support(self, message: str, user_id: Optional[str], correlation_id: str) -> Dict[str, object]:
        start = time.perf_counter()
        self.metrics.total_requests += 1
        masked_user = _mask_pii(user_id)
        tools_used: list[str] = []

        profile: Optional[UserProfile]
        profile_updates: Dict[str, Optional[str]]
        profile, profile_updates = self._profile_tool.extract_and_store(user_id, message)
        if profile:
            tools_used.append("user_profile")
        profile_masked = self._profile_tool.snapshot(profile)
        updated_fields = sorted(profile_updates.keys())
        if updated_fields:
            logger.info(
                "support.profile.updated",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": masked_user,
                    "fields": updated_fields,
                },
            )

        logger.info(
            "support.start",
            extra={
                "correlation_id": correlation_id,
                "user_id": masked_user,
                "message_chars": len(message or ""),
            },
        )

        account_status = self._account_tool.lookup(message, user_id=user_id, profile=profile)
        if account_status:
            tools_used.append("account_status")
            latency_ms = _elapsed_ms(start)
            logger.info(
                "support.account_status",
                extra={
                    "correlation_id": correlation_id,
                    "trigger": account_status.matched_trigger,
                    "status": account_status.record.status,
                    "latency_ms": latency_ms,
                },
            )
            self._log_finish(latency_ms, correlation_id)
            return {
                "faq_result": None,
                "ticket": None,
                "policy": None,
                "latency_ms": latency_ms,
                "account_status": account_status,
                "profile_masked": profile_masked,
                "profile_fields": updated_fields,
                "tools_used": tools_used,
            }

        faq_result = self._search_faq(message)
        if faq_result:
            self.metrics.faq_hits += 1
            latency_ms = _elapsed_ms(start)
            logger.info(
                "support.faq_hit",
                extra={
                    "correlation_id": correlation_id,
                    "faq_id": faq_result.item.id,
                    "score": faq_result.score,
                    "latency_ms": latency_ms,
                },
            )
            self._log_finish(latency_ms, correlation_id)
            return {
                "faq_result": faq_result,
                "ticket": None,
                "policy": None,
                "latency_ms": latency_ms,
                "account_status": None,
                "profile_masked": profile_masked,
                "profile_fields": updated_fields,
                "tools_used": tools_used + ["faq"],
            }

        policy = decide(message)
        ticket = self._create_ticket(message, user_id, policy, profile_masked)
        latency_ms = _elapsed_ms(start)

        logger.info(
            "support.ticket_created",
            extra={
                "correlation_id": correlation_id,
                "ticket_id": ticket.id,
                "priority": ticket.priority,
                "category": ticket.category,
                "escalation": ticket.escalation,
                "latency_ms": latency_ms,
            },
        )
        self._log_finish(latency_ms, correlation_id)

        return {
            "faq_result": None,
            "ticket": ticket,
            "policy": policy,
            "latency_ms": latency_ms,
            "account_status": None,
            "profile_masked": profile_masked,
            "profile_fields": updated_fields,
            "tools_used": tools_used + ["support_policy", "ticket"],
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
            user_ref=_mask_pii(ticket.user_id) if ticket.user_id else None,
        )

    def list_tickets_by_user(self, user_id: str) -> list[Ticket]:
        return self._ticket_tool.list_by_user(user_id)

    def _search_faq(self, message: str) -> Optional[FAQResult]:
        if not settings.support_faq_enabled:
            return None
        return self._faq_tool.search(FAQQuery(message))

    def _create_ticket(
        self,
        message: str,
        user_id: Optional[str],
        policy: PolicyDecision,
        profile_snapshot: Optional[Dict[str, Optional[str]]],
    ) -> Ticket:
        create_request = TicketCreateRequest(
            summary=_build_summary(message),
            description=_normalise_description(message),
            user_id=user_id,
            category=policy.category,
            priority=policy.priority,
            escalation=policy.escalation,
            profile_snapshot=profile_snapshot,
        )
        ticket = self._ticket_tool.create(create_request)
        self.metrics.tickets_created += 1
        if ticket.escalation:
            self.metrics.escalations += 1
        return ticket

    def _log_finish(self, latency_ms: float, correlation_id: str) -> None:
        self.metrics.add_latency(latency_ms)
        logger.info(
            "support.finish",
            extra={
                "correlation_id": correlation_id,
                "latency_ms": latency_ms,
                "total_requests": self.metrics.total_requests,
                "faq_hits": self.metrics.faq_hits,
                "tickets_created": self.metrics.tickets_created,
                "escalations": self.metrics.escalations,
                "avg_latency_ms": self.metrics.average_latency_ms,
                "p95_latency_ms": self.metrics.p95_latency_ms,
            },
        )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _build_summary(message: str) -> str:
    text = (message or "").strip().split(".")[0]
    if len(text) > 120:
        text = text[:117] + "..."
    return text or "Support"


def _normalise_description(message: str) -> str:
    text = (message or "").strip()
    text = re.sub(r"\s+", " ", text)
    limit = settings.support_max_response_chars
    if limit and len(text) > limit:
        text = text[:limit]
    return text


_support_service: Optional[SupportService] = None


def get_support_service() -> SupportService:
    global _support_service
    if _support_service is None:
        _support_service = SupportService()
    return _support_service
