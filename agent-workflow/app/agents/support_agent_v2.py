from __future__ import annotations

import logging
from typing import Optional

from app.agents.base import Agent, AgentControlledError, AgentRequest, AgentResponse
from app.services.support_service import SupportService
from app.settings import settings

logger = logging.getLogger(__name__)


class CustomerSupportAgent(Agent):
    name = "support"

    def __init__(self, service: Optional[SupportService] = None) -> None:
        self._service = service or SupportService()

    def run(self, payload: AgentRequest) -> AgentResponse:
        correlation_id = (payload.metadata or {}).get("correlation_id") if payload.metadata else None
        correlation_id = correlation_id or "support"
        try:
            result = self._service.handle_support(payload.message, payload.user_id, correlation_id)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("support.agent.error", extra={"correlation_id": correlation_id})
            raise AgentControlledError(
                error="support_agent_unavailable",
                status_code=503,
                details="We could not process the support request at this time.",
                agent=self.name,
            ) from exc

        faq_result = result["faq_result"]
        ticket = result["ticket"]
        policy = result["policy"]
        account_status = result.get("account_status")
        profile_masked = result.get("profile_masked")
        profile_fields = result.get("profile_fields", [])
        tools_used = result.get("tools_used", [])

        meta = {
            "faq_hit": bool(faq_result),
            "ticket_id": ticket.id if ticket else None,
            "priority": policy.priority if policy else None,
            "category": (policy.category if policy else (faq_result.item.categoria if faq_result else None)),
            "escalation_suggested": policy.escalation if policy else False,
            "support_latency_ms": result["latency_ms"],
            "faq_score": faq_result.score if faq_result else None,
            "faq_explanation": faq_result.explanation if faq_result else None,
            "tools_used": tools_used,
        }

        if profile_masked:
            meta["user_profile"] = profile_masked
            if profile_fields:
                meta["user_profile_fields"] = profile_fields

        if account_status:
            content = _compose_account_status_response(account_status)
            citations = [
                {
                    "title": "Status da conta",
                    "url": account_status.record.url,
                    "source_type": "infinitepay",
                }
            ]
            meta["account_status"] = account_status.as_dict()
        elif faq_result:
            faq = faq_result.item
            content = faq.resposta
            citations = [
                {
                    "title": faq.pergunta,
                    "url": "https://www.infinitepay.io",
                    "source_type": "infinitepay",
                }
            ]
        else:
            content, ticket_meta = _compose_ticket_response(ticket)
            meta.update(ticket_meta)
            citations = [
                {
                    "title": "Support ticket",
                    "url": "https://www.infinitepay.io/support",
                    "source_type": "infinitepay",
                }
            ]

        content = _normalise_answer(content)
        max_chars = settings.support_max_response_chars
        if max_chars and len(content) > max_chars:
            content = content[: max_chars - 3] + "..."

        return AgentResponse(agent=self.name, content=content, citations=citations, meta=meta)


def _compose_ticket_response(ticket) -> tuple[str, dict]:
    parts = [
        f"I have registered your request with ticket number {ticket.id}.",
        f"Category: {ticket.category.title()} | Priority: {ticket.priority.title()}.",
    ]
    meta: dict = {
        "ticket_summary": ticket.summary,
        "ticket_description": ticket.description,
    }
    if ticket.escalation:
        parts.append(
            "We identified a high impact. May I involve a human specialist on Slack to accelerate the follow-up? Reply 'yes' to confirm or 'no' to continue here."
        )
        meta.update(
            {
                "handoff_status": "pending",
                "handoff_channel": "slack",
                "handoff_source": "support",
            }
        )
    else:
        parts.append("Our team will reach out soon with updates.")
    return " ".join(parts), meta


def _normalise_answer(text: str) -> str:
    return " ".join((text or "").strip().split())


def _compose_account_status_response(status: "AccountStatusResult") -> str:
    details = status.record
    lines = [
        "Detectamos que suas transferências estão temporariamente bloqueadas por segurança.",
        details.reason,
    ]
    if details.limit:
        lines.append(f"Limite atual: {details.limit}.")
    lines.append(details.next_steps)
    lines.append("Liberaremos as transferências assim que a validação for concluída.")
    return " ".join(line.strip() for line in lines if line)
