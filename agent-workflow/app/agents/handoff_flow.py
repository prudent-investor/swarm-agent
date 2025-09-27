from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional

from app.settings import settings

_CONFIRM_TERMS = {
    "sim",
    "claro",
    "por favor",
    "pode",
    "positivo",
    "confirmo",
}
_CONFIRM_PHRASES = [
    "pode escalar",
    "pode chamar",
    "pode acionar",
    "quero falar com humano",
    "quero um humano",
    "me chama no slack",
    "atendimento humano",
]
_NEGATIVE_TERMS = {
    "nao",
    "negativo",
    "dispensa",
    "depois",
}
_NEGATIVE_PHRASES = [
    "nao precisa",
    "nao agora",
    "pode deixar",
]
_DIRECT_HUMAN_TERMS = {
    "humano",
    "atendente",
    "pessoa",
}


@dataclass
class PendingHandoff:
    token: str
    correlation_id: Optional[str]
    user_id: Optional[str]
    channel: str
    ticket_id: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    summary: str
    details: str
    created_at: float
    source: str

    @property
    def expires_at(self) -> float:
        return self.created_at + settings.handoff_confirm_ttl_seconds


class HandoffFlow:
    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        self._ttl = ttl_seconds or settings.handoff_confirm_ttl_seconds
        self._lock = threading.Lock()
        self._pending: Dict[str, PendingHandoff] = {}
        self._by_corr: Dict[str, str] = {}
        self._by_user: Dict[str, str] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired_tokens = [token for token, item in self._pending.items() if item.expires_at < now]
        for token in expired_tokens:
            self._remove(token)

    def _remove(self, token: str) -> None:
        item = self._pending.pop(token, None)
        if not item:
            return
        if item.correlation_id and self._by_corr.get(item.correlation_id) == token:
            self._by_corr.pop(item.correlation_id, None)
        if item.user_id and self._by_user.get(item.user_id) == token:
            self._by_user.pop(item.user_id, None)

    def register(
        self,
        *,
        correlation_id: Optional[str],
        user_id: Optional[str],
        ticket_id: Optional[str],
        category: Optional[str],
        priority: Optional[str],
        summary: str,
        details: str,
        source: str,
    ) -> PendingHandoff:
        with self._lock:
            self._cleanup()
            token = uuid.uuid4().hex
            item = PendingHandoff(
                token=token,
                correlation_id=correlation_id,
                user_id=user_id,
                channel="slack",
                ticket_id=ticket_id,
                category=category,
                priority=priority,
                summary=summary,
                details=details,
                created_at=time.time(),
                source=source,
            )
            self._pending[token] = item
            if correlation_id:
                self._by_corr[correlation_id] = token
            if user_id:
                self._by_user[user_id] = token
            return item

    def fetch(self, *, correlation_id: Optional[str], user_id: Optional[str], token: Optional[str]) -> Optional[PendingHandoff]:
        with self._lock:
            self._cleanup()
            if token and token in self._pending:
                return self._pending[token]
            if correlation_id and correlation_id in self._by_corr:
                stored_token = self._by_corr[correlation_id]
                return self._pending.get(stored_token)
            if user_id and user_id in self._by_user:
                stored_token = self._by_user[user_id]
                return self._pending.get(stored_token)
            return None

    def pop(self, *, correlation_id: Optional[str], user_id: Optional[str], token: Optional[str]) -> Optional[PendingHandoff]:
        with self._lock:
            self._cleanup()
            target: Optional[str] = None
            if token and token in self._pending:
                target = token
            elif correlation_id and correlation_id in self._by_corr:
                target = self._by_corr[correlation_id]
            elif user_id and user_id in self._by_user:
                target = self._by_user[user_id]
            if target:
                item = self._pending.get(target)
                if item:
                    self._remove(target)
                return item
            return None

    def clear(self, *, correlation_id: Optional[str], user_id: Optional[str], token: Optional[str]) -> None:
        self.pop(correlation_id=correlation_id, user_id=user_id, token=token)

    @staticmethod
    def normalise(text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"\s+", " ", text)
        return cleaned.strip().lower()

    def classify_confirmation(self, message: str) -> str:
        text = self.normalise(message)
        if not text:
            return "ambiguous"
        for phrase in _NEGATIVE_PHRASES:
            if phrase in text:
                return "deny"
        for phrase in _CONFIRM_PHRASES:
            if phrase in text:
                return "confirm"
        words = set(text.split())
        if words & _NEGATIVE_TERMS:
            return "deny"
        if words & _CONFIRM_TERMS:
            return "confirm"
        if any(term in text for term in _DIRECT_HUMAN_TERMS) and ("quero" in text or "preciso" in text or "fala" in text or "falar" in text):
            return "confirm"
        return "ambiguous"

    def is_direct_request(self, message: str) -> bool:
        text = self.normalise(message)
        if not text:
            return False
        if any(term in text for term in _NEGATIVE_TERMS):
            return False
        if any(term in text for term in _DIRECT_HUMAN_TERMS):
            if "quero" in text or "preciso" in text or "falar" in text or "fala" in text:
                return True
        for phrase in _CONFIRM_PHRASES:
            if phrase in text:
                return True
        return False


_handoff_flow: Optional[HandoffFlow] = None


def get_handoff_flow() -> HandoffFlow:
    global _handoff_flow
    if _handoff_flow is None:
        _handoff_flow = HandoffFlow()
    return _handoff_flow
