from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agents.base import (
    Agent,
    AgentControlledError,
    AgentRequest,
    AgentResponse,
    Route,
    RoutingDecision,
)
from app.agents.custom_agent import CustomAgent
from app.agents.handoff_flow import HandoffFlow, PendingHandoff, get_handoff_flow
from app.agents.knowledge_agent_v2 import KnowledgeAgent
from app.agents.router_agent import RouterAgent, router_agent as default_router_agent
from app.agents.slack_agent import SlackAgent, get_slack_agent
from app.agents.support_agent_v2 import CustomerSupportAgent
from app.guardrails import get_guardrails_service
from app.guardrails.violations import GuardrailViolation
from app.observability.metrics import get_metrics_registry
from app.schemas import ChatRequest, ChatResponse, ChatResponseMeta, HandoffConfirmation
from app.services.llm_provider import LLMProvider
from app.services.rag import HeuristicReranker, QueryCache, RAGRetriever
from app.services.redirect_service import get_redirect_service
from app.services.support_service import get_support_service
from app.services.web_search import NoopWebSearchClient
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()
_MAX_CONTENT_LENGTH = 2000

_shared_retriever = RAGRetriever()
_shared_reranker = HeuristicReranker()
_shared_cache = QueryCache(ttl_seconds=settings.rag_cache_ttl_seconds)
_shared_web_search = NoopWebSearchClient()
_DEFAULT_MANUAL_CITATION = {
    "title": "Support ticket",
    "url": "https://www.infinitepay.io/support",
    "source_type": "infinitepay",
}
_GUARDRAIL_CITATION = {
    "title": "Safety policy",
    "url": "https://www.infinitepay.io/safety",
    "source_type": "infinitepay",
}
_support_service = get_support_service()
_handoff_flow: HandoffFlow = get_handoff_flow()
_slack_agent = get_slack_agent()
_guardrails_service = get_guardrails_service()
_redirect_service = get_redirect_service()
_metrics = get_metrics_registry()


def _normalise_content(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) > _MAX_CONTENT_LENGTH:
        cleaned = cleaned[:_MAX_CONTENT_LENGTH].rstrip()
    return cleaned


def _guardrail_log_fields(meta: Dict[str, object]) -> Dict[str, object]:
    keys = [
        "guardrails_mode",
        "guardrails_accents_stripped",
        "guardrails_injection_detected",
        "guardrails_pii_masked",
        "guardrails_pii_masked_response",
        "guardrails_pre_ms",
        "guardrails_post_ms",
        "guardrails_total_ms",
        "guardrails_masked_input_preview",
        "moderation_blocked",
        "moderation_reason",
        "output_truncated",
    ]
    return {key: meta.get(key) for key in keys if key in meta}


def _apply_guardrail_meta(
    base_meta: Dict[str, object],
    pre_flags: Dict[str, object],
    pre_latency: float,
    post_result,
) -> Dict[str, object]:
    meta = dict(base_meta)
    meta.update(pre_flags)

    pre_ms = round(pre_latency, 3)
    post_ms = round(post_result.latency_ms, 3)
    meta["guardrails_pre_ms"] = pre_ms
    meta["guardrails_post_ms"] = post_ms
    meta["guardrails_total_ms"] = round(pre_ms + post_ms, 3)

    for key, value in post_result.flags.items():
        meta[f"guardrails_{key}"] = value

    blocked = bool(post_result.flags.get("moderation_blocked"))
    meta["moderation_blocked"] = bool(meta.get("moderation_blocked")) or blocked
    if post_result.flags.get("moderation_reason"):
        meta["moderation_reason"] = post_result.flags.get("moderation_reason")

    truncated = bool(post_result.flags.get("output_truncated"))
    meta["output_truncated"] = bool(meta.get("output_truncated")) or truncated

    pii_masked = bool(pre_flags.get("guardrails_pii_masked")) or bool(post_result.flags.get("pii_masked_response"))
    meta["pii_masked"] = bool(meta.get("pii_masked")) or pii_masked

    preview_key = "guardrails_masked_input_preview"
    if preview_key in meta and meta[preview_key] is not None:
        meta[preview_key] = str(meta[preview_key])[:200]

    meta.setdefault("guardrails_mode", settings.guardrails_mode)
    return meta


def _guardrail_flags(meta: Dict[str, object]) -> Dict[str, object]:
    return {
        "accents_stripped": bool(meta.get("guardrails_accents_stripped")),
        "injection_detected": bool(meta.get("guardrails_injection_detected")),
        "pii_masked": bool(meta.get("guardrails_pii_masked")),
        "moderation_blocked": bool(meta.get("moderation_blocked")),
        "output_truncated": bool(meta.get("output_truncated")),
    }


def _log_event(
    level: int,
    message: str,
    *,
    correlation_id: str,
    route: Optional[Route] = None,
    agent: Optional[str] = None,
    latency_ms: Optional[float] = None,
    flags: Optional[Dict[str, object]] = None,
    **extra: object,
) -> None:
    payload: Dict[str, object] = {
        "correlation_id": correlation_id,
        "route": route.value if isinstance(route, Route) else route,
        "agent": agent,
        "latency_ms": latency_ms,
        "flags": flags or {},
    }
    payload.update(extra)
    logger.log(level, message, extra=payload)


def _format_guardrail_violation_content(violations: List[GuardrailViolation]) -> str:
    if not violations:
        return (
            "I cannot continue with this request because it violates our safety policies. "
            "Please revise your request without restricted content."
        )
    lines = ["I cannot continue with this request because it violates our safety policies:"]
    for violation in violations:
        description = violation.description.rstrip(".")
        trigger = violation.trigger
        lines.append(f"- {description}. Triggered by '{trigger}'.")
    lines.append("Please revise your request without the restricted content.")
    return "\n".join(lines)


def _build_violation_meta(violations: List[GuardrailViolation]) -> Dict[str, object]:
    categories = sorted({violation.category for violation in violations})
    return {
        "guardrail_violation": True,
        "guardrail_violation_categories": categories,
        "guardrail_violations": [violation.as_dict() for violation in violations],
    }


def get_llm_provider() -> LLMProvider:
    return LLMProvider()


def get_router_agent() -> RouterAgent:
    return default_router_agent


def get_agents(provider: LLMProvider = Depends(get_llm_provider)) -> Dict[Route, Agent]:
    knowledge_agent = KnowledgeAgent(
        provider=provider,
        retriever=_shared_retriever,
        reranker=_shared_reranker,
        cache=_shared_cache,
        web_search=_shared_web_search,
    )
    support_agent = CustomerSupportAgent(service=_support_service)
    slack_agent = _slack_agent
    return {
        Route.knowledge: knowledge_agent,
        Route.support: support_agent,
        Route.custom: CustomAgent(provider),
        Route.slack: slack_agent,
    }

def _execute_agent(agent: Agent, request: AgentRequest, *, correlation_id: str) -> AgentResponse:
    try:
        return agent.run(request)
    except AgentControlledError as exc:
        _log_event(
            logging.WARNING,
            "chat.agent_controlled_error",
            correlation_id=correlation_id,
            agent=exc.agent or getattr(agent, "name", "unknown"),
            error=exc.error,
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": exc.error,
                "details": exc.details,
                "agent": exc.agent or getattr(agent, "name", None),
            },
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive guard for unexpected errors
        logger.exception(
            "chat.agent_unexpected_error",
            extra={
                "correlation_id": correlation_id,
                "agent": getattr(agent, "name", "unknown"),
                "route": None,
                "latency_ms": None,
                "flags": {},
            },
        )
        raise HTTPException(status_code=500, detail="Unexpected error while processing the request.") from exc


def _build_manual_response(
    *,
    agent: str,
    route: Route,
    content: str,
    correlation_id: str,
    latency_ms: float,
    pre_guardrail_flags: Optional[Dict[str, object]] = None,
    pre_guardrail_latency: float = 0.0,
    meta: Optional[Dict[str, object]] = None,
    citations: Optional[List[Dict[str, object]]] = None,
) -> ChatResponse:
    post_result = _guardrails_service.postprocess_output(content)
    meta_dict = meta or {}
    if pre_guardrail_flags is None:
        pre_guardrail_flags = {}
    meta_dict = _apply_guardrail_meta(meta_dict, pre_guardrail_flags, pre_guardrail_latency, post_result)
    meta_dict.setdefault("route", route.value)
    meta_dict["latency_ms"] = latency_ms
    meta_dict["correlation_id"] = correlation_id

    content_final = _normalise_content(post_result.content)
    meta_model = ChatResponseMeta(**meta_dict)

    _metrics.increment_chat_request(agent)
    _log_event(
        logging.INFO,
        "chat.success",
        correlation_id=correlation_id,
        agent=agent,
        route=route,
        latency_ms=latency_ms,
        flags=_guardrail_flags(meta_dict),
        **_guardrail_log_fields(meta_dict),
    )

    citations_payload = [dict(item) for item in (citations or [_DEFAULT_MANUAL_CITATION])]

    return ChatResponse(
        agent=agent,
        content=content_final,
        citations=citations_payload,
        meta=meta_model,
        correlation_id=correlation_id,
    )


def _register_handoff(
    *,
    correlation_id: str,
    user_id: Optional[str],
    meta: Dict[str, object],
    original_message: str,
) -> Optional[PendingHandoff]:
    ticket_id = meta.get("ticket_id")
    category = meta.get("category")
    priority = meta.get("priority")
    summary = meta.pop("ticket_summary", None) or original_message
    details = meta.pop("ticket_description", None) or original_message
    if not meta.get("escalation_suggested"):
        return None
    pending = _handoff_flow.register(
        correlation_id=correlation_id,
        user_id=user_id,
        ticket_id=ticket_id,
        category=category,
        priority=priority,
        summary=summary,
        details=details,
        source="support",
    )
    return pending

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    payload: ChatRequest,
    request: Request,
    router_agent: RouterAgent = Depends(get_router_agent),
    agents: Dict[Route, Agent] = Depends(get_agents),
) -> ChatResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid4())
    request.state.correlation_id = correlation_id
    start = time.perf_counter()

    pre_guardrails = _guardrails_service.preprocess_input(
        message=payload.message,
        user_id=payload.user_id,
        metadata=payload.metadata,
        origin="chat",
    )
    if getattr(request.state, "accents_stripped", False):
        pre_guardrails.flags["accents_stripped"] = True
    processed_message = pre_guardrails.message
    masked_preview = pre_guardrails.masked_preview()
    pre_flags = {f"guardrails_{key}": value for key, value in pre_guardrails.flags.items()}
    pre_flags["guardrails_mode"] = settings.guardrails_mode
    pre_flags["guardrails_masked_input_preview"] = masked_preview
    pre_flags["guardrails_input_chars"] = len(processed_message)
    if pre_guardrails.detected_injections:
        pre_flags["guardrails_injection_patterns"] = pre_guardrails.detected_injections

    start_flags = {
        "accents_stripped": pre_guardrails.flags.get("accents_stripped", False),
        "injection_detected": pre_guardrails.flags.get("injection_detected", False),
        "pii_masked": pre_guardrails.flags.get("pii_masked", False),
        "moderation_blocked": False,
        "output_truncated": False,
    }
    _log_event(
        logging.INFO,
        "chat.start",
        correlation_id=correlation_id,
        route=None,
        agent=None,
        latency_ms=0.0,
        flags=start_flags,
        user_id=(payload.user_id[:3] + "***") if payload.user_id else None,
        guardrails_mode=settings.guardrails_mode,
        guardrails_pre_ms=pre_guardrails.latency_ms,
        guardrails_masked_input_preview=masked_preview,
        guardrails_accents_stripped=pre_guardrails.flags.get("accents_stripped", False),
        guardrails_injection_detected=pre_guardrails.flags.get("injection_detected", False),
        guardrails_pii_masked=pre_guardrails.flags.get("pii_masked", False),
    )

    if pre_guardrails.violations:
        violations = pre_guardrails.violations
        violation_meta = _build_violation_meta(violations)
        violation_details = violation_meta["guardrail_violations"]
        pre_flags["guardrails_violation_blocked"] = True
        pre_flags.setdefault("guardrails_violations_details", violation_details)
        pre_flags.setdefault("guardrails_violation_categories", violation_meta["guardrail_violation_categories"])
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return _build_manual_response(
            agent="guardrails",
            route=Route.custom,
            content=_format_guardrail_violation_content(violations),
            correlation_id=correlation_id,
            latency_ms=latency_ms,
            pre_guardrail_flags=pre_flags,
            pre_guardrail_latency=pre_guardrails.latency_ms,
            meta=violation_meta,
            citations=[_GUARDRAIL_CITATION],
        )

    metadata = payload.metadata or {}

    token = metadata.get("handoff_token")
    pending = _handoff_flow.fetch(
        correlation_id=correlation_id,
        user_id=payload.user_id,
        token=token,
    )

    if pending:
        classification = _handoff_flow.classify_confirmation(processed_message)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if classification == "confirm":
            slack_agent = agents[Route.slack]
            merged_meta = {
                **metadata,
                "correlation_id": correlation_id,
                "handoff_action": "confirm",
                "handoff_token": pending.token,
            }
            agent_request = AgentRequest(message=processed_message, user_id=payload.user_id, metadata=merged_meta)
            agent_response = _execute_agent(slack_agent, agent_request, correlation_id=correlation_id)
            return _finalise_response(
                agent_response,
                route=Route.slack,
                correlation_id=correlation_id,
                start=start,
                pre_guardrail_flags=pre_flags,
                pre_guardrail_latency=pre_guardrails.latency_ms,
            )
        if classification == "deny":
            _handoff_flow.clear(correlation_id=correlation_id, user_id=payload.user_id, token=token)
            content = "All right, I will not escalate to human support now. Let me know if you change your mind."
            meta = {
                "handoff_status": "cancelled",
                "handoff_channel": "slack",
                "ticket_id": pending.ticket_id,
                "category": pending.category,
                "priority": pending.priority,
            }
            return _build_manual_response(
                agent="slack",
                route=Route.slack,
                content=content,
                correlation_id=correlation_id,
                latency_ms=latency_ms,
                pre_guardrail_flags=pre_flags,
                pre_guardrail_latency=pre_guardrails.latency_ms,
                meta=meta,
            )

        content = "I did not understand. Reply with 'yes' to reach the human team or 'no' to continue here."
        meta = {
            "handoff_status": "pending",
            "handoff_channel": "slack",
            "handoff_token": pending.token,
            "ticket_id": pending.ticket_id,
            "category": pending.category,
            "priority": pending.priority,
        }
        return _build_manual_response(
            agent="slack",
            route=Route.slack,
            content=content,
            correlation_id=correlation_id,
            latency_ms=latency_ms,
            pre_guardrail_flags=pre_flags,
            pre_guardrail_latency=pre_guardrails.latency_ms,
            meta=meta,
        )

    if _handoff_flow.is_direct_request(processed_message):
        slack_agent = agents[Route.slack]
        merged_meta = {
            **metadata,
            "correlation_id": correlation_id,
            "handoff_action": "request",
            "handoff_summary": processed_message,
            "handoff_details": processed_message,
            "handoff_source": "direct",
        }
        agent_request = AgentRequest(message=processed_message, user_id=payload.user_id, metadata=merged_meta)
        agent_response = _execute_agent(slack_agent, agent_request, correlation_id=correlation_id)
        return _finalise_response(
            agent_response,
            route=Route.slack,
            correlation_id=correlation_id,
            start=start,
            pre_guardrail_flags=pre_flags,
            pre_guardrail_latency=pre_guardrails.latency_ms,
        )
    try:
        decision: RoutingDecision = router_agent.route_message(processed_message)
    except RuntimeError as exc:
        logger.exception(
            "chat.routing_failed",
            extra={
                "correlation_id": correlation_id,
                "route": None,
                "agent": None,
                "latency_ms": None,
                "flags": {},
            },
        )
        raise HTTPException(status_code=502, detail="Intent router temporarily unavailable.") from exc

    route = decision.route

    redirect_result = _redirect_service.evaluate(
        message=processed_message,
        route=route,
        confidence=decision.confidence,
        user_id=payload.user_id,
        metadata=metadata,
    )
    if redirect_result:
        _metrics.increment_redirect()
        _log_event(
            logging.INFO,
            "chat.redirect",
            correlation_id=correlation_id,
            route=route,
            agent=redirect_result.response.agent,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            flags={},
            redirect=True,
            redirect_reason=redirect_result.reason,
        )
        return _finalise_response(
            redirect_result.response,
            route=route,
            correlation_id=correlation_id,
            start=start,
            pre_guardrail_flags=pre_flags,
            pre_guardrail_latency=pre_guardrails.latency_ms,
        )

    agent = agents.get(route)
    if agent is None:
        agent = agents[Route.custom]

    agent_metadata = {"correlation_id": correlation_id, **metadata, "original_message": payload.message}
    if route == Route.slack and agent_metadata.get("handoff_action") is None:
        agent_metadata.update({
            "handoff_action": "request",
            "handoff_summary": processed_message,
            "handoff_details": processed_message,
            "handoff_source": "router",
        })
    agent_request = AgentRequest(message=processed_message, user_id=payload.user_id, metadata=agent_metadata)
    agent_response = _execute_agent(agent, agent_request, correlation_id=correlation_id)

    if route == Route.support and agent_response.meta and agent_response.meta.get("escalation_suggested"):
        meta_dict = dict(agent_response.meta)
        pending_request = _register_handoff(
            correlation_id=correlation_id,
            user_id=payload.user_id,
            meta=meta_dict,
            original_message=payload.message,
        )
        if pending_request:
            meta_dict.update(
                {
                    "handoff_status": "pending",
                    "handoff_channel": "slack",
                    "handoff_token": pending_request.token,
                    "handoff_request": HandoffConfirmation(
                        token=pending_request.token,
                        channel=pending_request.channel,
                        ticket_id=pending_request.ticket_id,
                        category=pending_request.category,
                        priority=pending_request.priority,
                        expires_at=pending_request.expires_at,
                    ).model_dump(),
                }
            )
            agent_response = AgentResponse(
                agent=agent_response.agent,
                content=agent_response.content,
                citations=agent_response.citations,
                meta=meta_dict,
            )

    return _finalise_response(
        agent_response,
        route=route,
        correlation_id=correlation_id,
        start=start,
        pre_guardrail_flags=pre_flags,
        pre_guardrail_latency=pre_guardrails.latency_ms,
    )


def _finalise_response(
    agent_response: AgentResponse,
    *,
    route: Route,
    correlation_id: str,
    start: float,
    pre_guardrail_flags: Dict[str, object],
    pre_guardrail_latency: float,
) -> ChatResponse:
    post_result = _guardrails_service.postprocess_output(agent_response.content)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    meta_dict = dict(agent_response.meta or {})
    meta_dict = _apply_guardrail_meta(meta_dict, pre_guardrail_flags, pre_guardrail_latency, post_result)
    meta_dict.setdefault("route", route.value)
    meta_dict["latency_ms"] = latency_ms
    meta_dict["correlation_id"] = correlation_id

    content = _normalise_content(post_result.content)
    meta = ChatResponseMeta(**meta_dict)

    _metrics.increment_chat_request(agent_response.agent)
    _log_event(
        logging.INFO,
        "chat.success",
        correlation_id=correlation_id,
        agent=agent_response.agent,
        route=route,
        latency_ms=latency_ms,
        flags=_guardrail_flags(meta_dict),
        **_guardrail_log_fields(meta_dict),
    )

    return ChatResponse(
        agent=agent_response.agent,
        content=content,
        citations=agent_response.citations,
        meta=meta,
        correlation_id=correlation_id,
    )
