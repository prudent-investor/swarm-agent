from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class SlackResult:
    ok: bool
    message_id: Optional[str]
    channel: Optional[str]
    error: Optional[str] = None


@dataclass
class SlackPayload:
    channel: str
    text: str
    blocks: list

    def as_dict(self) -> dict:
        return {
            "channel": self.channel,
            "text": self.text,
            "blocks": self.blocks,
        }


class SlackClient(Protocol):
    def send_message(self, payload: SlackPayload) -> SlackResult:
        ...


class MockSlackClient:
    def send_message(self, payload: SlackPayload) -> SlackResult:  # type: ignore[override]
        message_id = f"mock-{int(time.time() * 1000)}"
        logger.info(
            "slack.mock.send",
            extra={"channel": payload.channel, "message_id": message_id},
        )
        return SlackResult(ok=True, message_id=message_id, channel=payload.channel)


class RealSlackClient:
    def __init__(self, *, webhook_url: Optional[str], bot_token: Optional[str], timeout: float, retries: int) -> None:
        self._webhook_url = webhook_url
        self._bot_token = bot_token
        self._timeout = timeout
        self._retries = retries

    def send_message(self, payload: SlackPayload) -> SlackResult:  # type: ignore[override]
        if not self._webhook_url and not self._bot_token:
            return SlackResult(ok=False, message_id=None, channel=payload.channel, error="slack_credentials_missing")

        data = payload.as_dict()
        error: Optional[str] = None
        for attempt in range(self._retries + 1):
            try:
                if self._webhook_url:
                    response = httpx.post(
                        self._webhook_url,
                        json=data,
                        timeout=self._timeout,
                    )
                else:
                    response = httpx.post(
                        "https://slack.com/api/chat.postMessage",
                        headers={
                            "Authorization": f"Bearer {self._bot_token}",
                            "Content-Type": "application/json; charset=utf-8",
                        },
                        json=data,
                        timeout=self._timeout,
                    )
            except httpx.TimeoutException:
                error = "timeout"
            except httpx.HTTPError as exc:  # pragma: no cover - network failure
                error = str(exc)
            else:
                if response.status_code >= 400:
                    error = f"http_{response.status_code}"
                else:
                    payload_json = response.json() if "application/json" in response.headers.get("Content-Type", "") else {}
                    if payload_json.get("ok", True):
                        message_id = payload_json.get("ts") or payload_json.get("message", {}).get("ts")
                        if not message_id:
                            message_id = response.headers.get("X-Slack-Req-Id") or f"real-{int(time.time() * 1000)}"
                        return SlackResult(ok=True, message_id=message_id, channel=data["channel"])
                    error = payload_json.get("error", "unknown_error")
            time.sleep(0.5 * (attempt + 1))
        logger.error(
            "slack.real.send_failed",
            extra={"channel": payload.channel, "error": error},
        )
        return SlackResult(ok=False, message_id=None, channel=payload.channel, error=error)


_client: Optional[SlackClient] = None


def get_slack_client() -> SlackClient:
    global _client
    if _client is None:
        if settings.slack_enabled and settings.slack_mode == "real":
            _client = RealSlackClient(
                webhook_url=settings.slack_webhook_url,
                bot_token=settings.slack_bot_token,
                timeout=settings.slack_timeout_seconds,
                retries=max(0, settings.slack_max_retries),
            )
        else:
            _client = MockSlackClient()
    return _client
