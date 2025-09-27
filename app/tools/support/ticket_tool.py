from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from app.settings import settings

from .contracts import Ticket, TicketCreateRequest

logger = logging.getLogger(__name__)


class TicketTool:
    def __init__(self, *, persist_to_file: Optional[bool] = None, file_path: Optional[Path] = None) -> None:
        self._persist = settings.support_tickets_persist_to_file if persist_to_file is None else persist_to_file
        self._file_path = Path(settings.support_tickets_file_path) if file_path is None else file_path
        self._tickets: Dict[str, Ticket] = {}
        self._lock = threading.Lock()
        if self._persist:
            self._load_from_file()

    def _load_from_file(self) -> None:
        if not self._file_path.exists():
            return
        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("support.ticket.persistence_invalid", extra={"error": str(exc)})
            return
        for record in payload:
            ticket = Ticket(
                id=record["id"],
                summary=record["summary"],
                description=record["description"],
                user_id=record.get("user_id"),
                status=record.get("status", "open"),
                priority=record.get("priority", "medium"),
                category=record.get("category", "outros"),
                channel=record.get("channel", "chat"),
                created_at=datetime.fromisoformat(record["created_at"]),
                updated_at=datetime.fromisoformat(record["updated_at"]),
                escalation=record.get("escalation", False),
                internal_notes=record.get("internal_notes"),
            )
            self._tickets[ticket.id] = ticket

    def _persist_to_file(self) -> None:
        if not self._persist:
            return
        data = []
        for ticket in self._tickets.values():
            data.append(
                {
                    "id": ticket.id,
                    "summary": ticket.summary,
                    "description": ticket.description,
                    "user_id": ticket.user_id,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "category": ticket.category,
                    "channel": ticket.channel,
                    "created_at": ticket.created_at.isoformat(),
                    "updated_at": ticket.updated_at.isoformat(),
                    "escalation": ticket.escalation,
                    "internal_notes": ticket.internal_notes,
                }
            )
        temp_path = self._file_path.with_suffix(".tmp")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self._file_path)

    def create(self, request: TicketCreateRequest) -> Ticket:
        with self._lock:
            ticket_id = self._generate_id()
            now = datetime.now(timezone.utc)
            ticket = Ticket(
                id=ticket_id,
                summary=request.summary,
                description=request.description,
                user_id=request.user_id,
                status="open",
                priority=request.priority,
                category=request.category,
                channel=request.channel,
                created_at=now,
                updated_at=now,
                escalation=request.escalation,
            )
            self._tickets[ticket.id] = ticket
            try:
                self._persist_to_file()
            except OSError as exc:  # pragma: no cover
                logger.error("support.ticket.persistence_failed", extra={"error": str(exc)})
            return ticket

    def get(self, ticket_id: str) -> Optional[Ticket]:
        return self._tickets.get(ticket_id)

    def list_by_user(self, user_id: str) -> List[Ticket]:
        return [ticket for ticket in self._tickets.values() if ticket.user_id == user_id]

    def _generate_id(self) -> str:
        base = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        suffix = int(time.time() * 1000) % 1000
        return f"SUP-{base}-{suffix:03d}"

