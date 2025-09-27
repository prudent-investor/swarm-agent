from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class FAQItem:
    id: str
    pergunta: str
    resposta: str
    tags: List[str]
    categoria: str
    atualizado_em: str


@dataclass
class FAQResult:
    item: FAQItem
    score: float
    explanation: str


@dataclass
class FAQQuery:
    message: str


@dataclass
class TicketCreateRequest:
    summary: str
    description: str
    user_id: Optional[str]
    category: str
    priority: str
    channel: str = "chat"
    escalation: bool = False


@dataclass
class Ticket:
    id: str
    summary: str
    description: str
    user_id: Optional[str]
    status: str
    priority: str
    category: str
    channel: str
    created_at: datetime
    updated_at: datetime
    escalation: bool = False
    internal_notes: Optional[str] = None


@dataclass
class TicketPublicView:
    id: str
    status: str
    created_at: str
    updated_at: str
    priority: str
    category: str
    summary: str
    user_ref: Optional[str]
