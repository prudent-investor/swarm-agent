from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, constr
from pydantic.config import ConfigDict


class CitationSource(str, Enum):
    infinitepay = "infinitepay"
    external = "external"


class Citation(BaseModel):
    title: str
    url: constr(min_length=1)
    source_type: CitationSource = CitationSource.infinitepay


class ChatRequest(BaseModel):
    message: constr(min_length=1, max_length=4000)
    user_id: Optional[str] = Field(default=None, max_length=255)
    metadata: Optional[Dict[str, Any]] = None


class HandoffConfirmation(BaseModel):
    token: str
    channel: str = "slack"
    expires_at: float
    ticket_id: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None


class ChatResponseMeta(BaseModel):
    route: str
    latency_ms: float
    faq_hit: Optional[bool] = None
    ticket_id: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    escalation_suggested: Optional[bool] = None
    support_latency_ms: Optional[float] = None
    faq_score: Optional[float] = None
    faq_explanation: Optional[str] = None
    handoff_channel: Optional[str] = None
    handoff_status: Optional[str] = None
    handoff_message_id: Optional[str] = None
    handoff_token: Optional[str] = None
    handoff_latency_ms: Optional[float] = None
    handoff_error: Optional[str] = None
    handoff_request: Optional[HandoffConfirmation] = None

    model_config = ConfigDict(extra="allow")


class ChatResponse(BaseModel):
    agent: str
    content: str
    citations: List[Citation] = Field(default_factory=list)
    meta: Optional[ChatResponseMeta] = None
    correlation_id: Optional[str] = None


class TicketPublicResponse(BaseModel):
    id: str
    status: str
    created_at: str
    updated_at: str
    priority: str
    category: str
    summary: str
    user_ref: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    message: str
