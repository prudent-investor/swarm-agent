from __future__ import annotations

import re
import time
from dataclasses import dataclass
from itertools import count
from typing import Dict, Optional

from app.agents.base import AgentResponse, Route
from app.settings import settings

_HUMAN_REQUEST_PATTERNS = (
    r"falar\s+com\s+humano",
    r"falar\s+com\s+atendente",
    r"quero\s+um?\s+humano",
    r"preciso\s+de\s+humano",
    r"talk\s+to\s+(a\s+)?human",
    r"human\s+agent",
)

_TICKET_COUNTER = count(1)


@dataclass
class RedirectResult:
    response: AgentResponse
    reason: str


class RedirectService:
    def __init__(self) -> None:
        self._compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in _HUMAN_REQUEST_PATTERNS]

    def evaluate(
        self,
        *,
        message: str,
        route: Route,
        confidence: Optional[float],
        user_id: Optional[str],
        metadata: Optional[Dict[str, object]] = None,
    ) -> Optional[RedirectResult]:
        if not settings.redirect_enabled:
            return None

        if route == Route.slack:
            return None

        reason: Optional[str] = None

        if settings.guardrails_redirect_always:
            reason = "manual"
        elif confidence is not None and confidence < settings.redirect_confidence_threshold:
            reason = "low_confidence"
        elif self._has_explicit_human_request(message):
            reason = "explicit_request"
        elif metadata and isinstance(metadata.get("redirect_reason"), str):
            reason = metadata.get("redirect_reason") or None

        if not reason:
            return None

        response = self._build_response(reason=reason, user_id=user_id)
        return RedirectResult(response=response, reason=reason)

    def _has_explicit_human_request(self, message: str) -> bool:
        if not message:
            return False
        for pattern in self._compiled_patterns:
            if pattern.search(message):
                return True
        return False

    def _build_response(self, *, reason: str, user_id: Optional[str]) -> AgentResponse:
        ticket_id = self._generate_ticket_id()
        channel = settings.slack_channel_default if settings.slack_agent_enabled else "internal-routing"
        content = (
            "Your request was redirected to a human agent. A support ticket has been created."
        )
        meta: Dict[str, object] = {
            "redirect_reason": reason,
            "ticket_id": ticket_id,
            "channel": channel,
            "redirected": True,
        }
        if user_id:
            meta["user_id"] = user_id
        return AgentResponse(agent="redirect", content=content, citations=[], meta=meta)

    @staticmethod
    def _generate_ticket_id() -> str:
        sequence = next(_TICKET_COUNTER)
        prefix = time.strftime("%Y%m%d")
        return f"HUM-{prefix}-{sequence:03d}"


_redirect_service: Optional[RedirectService] = None


def get_redirect_service() -> RedirectService:
    global _redirect_service
    if _redirect_service is None:
        _redirect_service = RedirectService()
    return _redirect_service
