from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from app.settings import settings
from app.utils.text import strip_portuguese_accents
from app.utils.paths import get_support_data_dir


@dataclass
class AccountStatusRecord:
    id: str
    triggers: List[str]
    status: str
    reason: str
    limit: Optional[str]
    next_steps: str
    url: str

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "AccountStatusRecord":
        return cls(
            id=str(payload["id"]),
            triggers=[strip_portuguese_accents(str(item).lower()) for item in payload.get("triggers", [])],
            status=str(payload.get("status", "unknown")),
            reason=str(payload.get("reason", "")),
            limit=payload.get("limit"),
            next_steps=str(payload.get("next_steps", "")),
            url=str(payload.get("url", "https://www.infinitepay.io/conta-digital")),
        )


@dataclass
class AccountStatusResult:
    record: AccountStatusRecord
    matched_trigger: str

    def as_dict(self) -> Dict[str, object]:
        return {
            "id": self.record.id,
            "status": self.record.status,
            "reason": self.record.reason,
            "limit": self.record.limit,
            "next_steps": self.record.next_steps,
            "url": self.record.url,
            "trigger": self.matched_trigger,
        }


class AccountStatusTool:
    def __init__(self, *, dataset_path: Optional[Path] = None) -> None:
        default_path = get_support_data_dir() / "account_status.json"
        self._dataset_path = dataset_path or default_path
        self._records: List[AccountStatusRecord] = []
        self._load_records()

    def _load_records(self) -> None:
        if not self._dataset_path.exists():
            return
        try:
            payload = json.loads(self._dataset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._records = []
        for item in payload:
            try:
                record = AccountStatusRecord.from_dict(item)
            except Exception:
                continue
            self._records.append(record)

    def lookup(self, message: str, *, user_id: Optional[str] = None, profile: Optional[object] = None) -> Optional[AccountStatusResult]:
        if not message:
            return None
        if not settings.support_pii_masking_enabled:
            # even when masking is disabled, we still normalise accents for matching
            normalised = strip_portuguese_accents(message.lower())
        else:
            normalised = strip_portuguese_accents(message.lower())
        for record in self._records:
            for trigger in record.triggers:
                if trigger and trigger in normalised:
                    return AccountStatusResult(record=record, matched_trigger=trigger)
        return None

    def available_records(self) -> Iterable[AccountStatusRecord]:
        return tuple(self._records)
