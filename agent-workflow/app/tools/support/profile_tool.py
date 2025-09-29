from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from app.settings import settings
from app.utils.text import strip_portuguese_accents
from app.utils.paths import get_support_data_dir

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PLAN_PATTERNS: Dict[str, str] = {
    "plano pro": "pro",
    "pro plan": "pro",
    "sou pro": "pro",
    "plano start": "start",
    "plano smart": "smart",
    "plano completo": "completo",
    "plano gratuito": "gratis",
    "plano grátis": "gratis",
    "free plan": "gratis",
    "enterprise": "enterprise",
}


@dataclass
class UserProfile:
    user_id: str
    email: Optional[str] = None
    plan: Optional[str] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_masked_dict(self) -> Dict[str, Optional[str]]:
        return {
            "user_id": mask_email(self.user_id),
            "email": mask_email(self.email),
            "plan": self.plan,
            "last_updated": self.last_updated.isoformat(),
        }


def mask_email(value: Optional[str]) -> Optional[str]:
    if not value or not settings.support_pii_masking_enabled:
        return value
    username, _, domain = value.partition("@")
    if not username or not domain:
        return value
    if len(username) <= 2:
        return "**@" + domain
    return f"{username[:2]}***@{domain}"


class UserProfileTool:
    """Extracts and persists lightweight user profile data."""

    def __init__(
        self,
        *,
        persist_to_file: bool | None = None,
        file_path: Optional[Path] = None,
    ) -> None:
        self._persist = settings.support_tickets_persist_to_file if persist_to_file is None else persist_to_file
        default_path = get_support_data_dir() / "user_profiles.json"
        self._file_path = default_path if file_path is None else file_path
        self._profiles: Dict[str, UserProfile] = {}
        if self._persist:
            self._load()

    def _load(self) -> None:
        if not self._file_path.exists():
            return
        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for record in payload:
            try:
                profile = UserProfile(
                    user_id=str(record["user_id"]),
                    email=record.get("email"),
                    plan=record.get("plan"),
                    last_updated=datetime.fromisoformat(record["last_updated"]),
                )
            except (KeyError, ValueError, TypeError):
                continue
            self._profiles[profile.user_id] = profile

    def _persist_profiles(self) -> None:
        if not self._persist:
            return
        data = [
            {
                "user_id": profile.user_id,
                "email": profile.email,
                "plan": profile.plan,
                "last_updated": profile.last_updated.isoformat(),
            }
            for profile in self._profiles.values()
        ]
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self._file_path)

    def get(self, user_id: str) -> Optional[UserProfile]:
        return self._profiles.get(user_id)

    def extract_and_store(self, user_id: Optional[str], message: str) -> tuple[Optional[UserProfile], Dict[str, Optional[str]]]:
        if not user_id:
            return None, {}
        profile = self._profiles.get(user_id) or UserProfile(user_id=user_id)
        updates: Dict[str, Optional[str]] = {}
        email = _find_email(message)
        plan = _find_plan(message)
        if email and email != profile.email:
            profile.email = email
            updates["email"] = email
        if plan and plan != profile.plan:
            profile.plan = plan
            updates["plan"] = plan
        if updates:
            profile.last_updated = datetime.now(timezone.utc)
            self._profiles[user_id] = profile
            self._persist_profiles()
        elif user_id not in self._profiles:
            self._profiles[user_id] = profile
        return profile, updates

    def snapshot(self, profile: Optional[UserProfile]) -> Optional[Dict[str, Optional[str]]]:
        if not profile:
            return None
        return profile.as_masked_dict()


def _find_email(message: str) -> Optional[str]:
    match = _EMAIL_PATTERN.search(message or "")
    return match.group(0).lower() if match else None


def _find_plan(message: str) -> Optional[str]:
    if not message:
        return None
    normalised = strip_portuguese_accents(message.lower())
    for pattern, label in _PLAN_PATTERNS.items():
        if pattern in normalised:
            return label
    return None
