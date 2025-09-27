from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, Optional

from app.agents.base import Agent, AgentRequest, AgentResponse
from app.agents.handoff_flow import PendingHandoff, get_handoff_flow
from app.services.slack import SlackContext, SlackPayload, SlackResult, build_slack_message, get_slack_client
from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class SlackMetrics:
    attempts: int = 0
    success: int = 0
    failed: int = 0
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
        ordered = sorted(self.latencies_ms)
        index = max(0, int(len(ordered) * 0.95) - 1)
        return round(ordered[index], 2)


class SlackAgent(Agent):
    name = "slack"

    def __init__(self, *, slack_client=None, handoff_flow=None) -> None:
        self._client = slack_client or get_slack_client()
        self._handoff = handoff_flow or get_handoff_flow()
        self.metrics = SlackMetrics()

    def run(self, payload: AgentRequest) -> AgentResponse:
        metadata = payload.metadata or {}
        correlation_id = metadata.get("correlation_id")
        token = metadata.get("handoff_token")
        action = metadata.get("handoff_action") or "confirm"
        source = metadata.get("handoff_source") or "manual"

        if action == "request":
            return self._handle_request(payload=payload, correlation_id=correlation_id, source=source)

        if action == "cancel":
            self._handoff.clear(correlation_id=correlation_id, user_id=payload.user_id, token=token)
            content = "No problem, we will keep helping you here. Let me know if you need to escalate again."
            return self._response(content, meta={
                "handoff_status": "cancelled",
                "handoff_channel": "slack",
            })

        return self._handle_confirm(payload, correlation_id=correlation_id, token=token)

    def _handle_request(self, *, payload: AgentRequest, correlation_id: Optional[str], source: str) -> AgentResponse:
        channel = settings.slack_channel_default
        if not settings.slack_agent_enabled:
            meta = {
                "handoff_status": "disabled",
                "handoff_channel": "slack",
                "channel": channel,
            }
            content = (
                "The human support channel is currently disabled. Our team will keep assisting you in this chat."
            )
            return self._response(content, meta=meta)

        summary = payload.metadata.get("handoff_summary") if payload.metadata else None
        details = payload.metadata.get("handoff_details") if payload.metadata else None
        summary = summary or payload.message
        details = details or payload.message

        pending = self._handoff.register(
            correlation_id=correlation_id,
            user_id=payload.user_id,
            ticket_id=payload.metadata.get("ticket_id") if payload.metadata else None,
            category=payload.metadata.get("category") if payload.metadata else None,
            priority=payload.metadata.get("priority") if payload.metadata else None,
            summary=summary,
            details=details,
            source=source,
        )

        meta = {
            "handoff_status": "pending",
            "handoff_channel": "slack",
            "handoff_token": pending.token,
            "ticket_id": pending.ticket_id,
            "category": pending.category,
            "priority": pending.priority,
            "channel": channel,
            "redirected": True,
        }
        content = f"I have notified the human support team in channel {channel}. They will review the case and follow up soon."
        return self._response(content, meta=meta)

    def _handle_confirm(self, payload: AgentRequest, *, correlation_id: Optional[str], token: Optional[str]) -> AgentResponse:
        pending = self._handoff.pop(correlation_id=correlation_id, user_id=payload.user_id, token=token)
        if not pending:
            content = "I could not find a pending escalation request. If you still need assistance, let me know and I will create one."
            return self._response(content, meta={"handoff_status": "not_found"})

        if not settings.slack_enabled:
            content = "The human escalation channel is temporarily unavailable. Our team will keep monitoring your request here."
            meta = {
                "handoff_status": "disabled",
                "handoff_channel": "slack",
                "ticket_id": pending.ticket_id,
                "category": pending.category,
                "priority": pending.priority,
            }
            return self._response(content, meta=meta)

        start = time.perf_counter()
        self.metrics.attempts += 1

        result = self._send_to_slack(pending, correlation_id or pending.correlation_id or "unknown")
        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.add_latency(latency_ms)

        meta = {
            "handoff_channel": "slack",
            "handoff_status": "ok" if result.ok else "failed",
            "handoff_message_id": result.message_id,
            "ticket_id": pending.ticket_id,
            "category": pending.category,
            "priority": pending.priority,
            "handoff_latency_ms": round(latency_ms, 2),
        }
        if not result.ok:
            meta["handoff_error"] = result.error

        content = (
            "I have engaged our human support team on Slack. They will monitor the case and respond shortly."
            if result.ok
            else "I could not reach the human support team right now, but I have already notified our internal staff."
        )

        return self._response(content, meta=meta)

    def _send_to_slack(self, pending: PendingHandoff, correlation_id: str) -> SlackResult:
        requested_by = _mask_value(pending.user_id)
        title = _compose_title(pending)
        links = []
        if pending.ticket_id:
            links.append(f"https://www.infinitepay.io/support/tickets/{pending.ticket_id}")

        context = SlackContext(
            channel=settings.slack_default_channel,
            title=title,
            summary=pending.summary,
            details=pending.details,
            ticket_id=pending.ticket_id,
            category=pending.category,
            priority=pending.priority,
            correlation_id=correlation_id,
            links=links,
            requested_by=requested_by,
        )
        message = build_slack_message(context)
        payload = SlackPayload(channel=message.channel, text=message.text, blocks=message.blocks)
        logger.info(
            "slack.handoff.attempt",
            extra={
                "channel": payload.channel,
                "correlation_id": correlation_id,
                "ticket_id": pending.ticket_id,
                "category": pending.category,
                "priority": pending.priority,
            },
        )
        result = self._client.send_message(payload)
        if result.ok:
            self.metrics.success += 1
            logger.info(
                "slack.handoff.success",
                extra={
                    "channel": result.channel,
                    "message_id": result.message_id,
                    "correlation_id": correlation_id,
                },
            )
        else:
            self.metrics.failed += 1
            logger.error(
                "slack.handoff.failed",
                extra={
                    "channel": payload.channel,
                    "error": result.error,
                    "correlation_id": correlation_id,
                },
            )
        return result

    @staticmethod
    def _normalise(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _response(self, content: str, meta: Optional[Dict[str, object]] = None) -> AgentResponse:
        meta = meta or {}
        meta.setdefault("handoff_channel", "slack")
        meta.setdefault("route", "slack")
        content = self._normalise(content)
        limit = settings.support_max_response_chars
        if limit and len(content) > limit:
            content = content[: limit - 3] + "..."
        citations = [
            {
                "title": "Suporte humano",
                "url": "https://www.infinitepay.io/suporte",
                "source_type": "infinitepay",
            }
        ]
        return AgentResponse(agent=self.name, content=content, citations=citations, meta=meta)


def _compose_title(pending: PendingHandoff) -> str:
    ticket_fragment = f"#{pending.ticket_id}" if pending.ticket_id else "#SEM-TICKET"
    category = pending.category or "sem-categoria"
    priority = pending.priority or "sem-prioridade"
    return f"[SUPPORT ESCALATION] {ticket_fragment} {category}/{priority}".upper()


def _mask_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if not settings.pii_masking_enabled:
        return value
    masked = re.sub(r"([\w._%+-]+)@([\w.-]+)", r"***@\2", value)
    masked = re.sub(r"\b\d{5,}\b", "***", masked)
    return masked


_slack_agent: Optional[SlackAgent] = None


def get_slack_agent() -> SlackAgent:
    global _slack_agent
    if _slack_agent is None:
        _slack_agent = SlackAgent()
    return _slack_agent
