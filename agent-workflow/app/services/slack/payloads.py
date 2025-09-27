from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from app.settings import settings

_EMAIL_RE = re.compile(r"([\w._%+-]+)@([\w.-]+)")
_PHONE_RE = re.compile(r"\b\+?\d[\d\-\s]{7,}\b")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SlackContext:
    channel: str
    title: str
    summary: str
    details: str
    ticket_id: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    correlation_id: str
    links: List[str]
    requested_by: Optional[str]


@dataclass
class SlackMessage:
    channel: str
    text: str
    blocks: List[dict]


def _truncate(text: str, limit: int) -> str:
    if limit and len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _mask_pii(text: str) -> str:
    if not text or not settings.pii_masking_enabled:
        return text or ""
    masked = _EMAIL_RE.sub(r"***@\2", text)
    masked = _PHONE_RE.sub("***", masked)
    masked = re.sub(r"\b\d{11,}\b", "***", masked)
    return masked


def _sanitize(text: str) -> str:
    if not text:
        return ""
    clean = _HTML_TAG_RE.sub(" ", text)
    clean = re.sub(r"https?://\S+", "[link]", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def build_slack_message(context: SlackContext) -> SlackMessage:
    summary_limit = settings.handoff_summary_max_chars
    details_limit = settings.handoff_details_max_chars

    summary = _sanitize(_mask_pii(context.summary))
    details = _sanitize(_mask_pii(context.details))
    summary = _truncate(summary, summary_limit)
    details = _truncate(details, details_limit)

    title = _truncate(_sanitize(_mask_pii(context.title)), 120)

    lines = [f"*{title}*", summary]
    if details:
        lines.append(details)

    if context.ticket_id:
        lines.append(f"Ticket: `{context.ticket_id}`")
    if context.category or context.priority:
        badge = "/".join(
            part for part in [context.category or "-", context.priority or "-"] if part
        )
        lines.append(f"Clas.: {badge}")
    if context.requested_by:
        lines.append(f"Solicitado por: {context.requested_by}")
    if context.links:
        for link in context.links[:3]:
            lines.append(f"Link: {link}")
    lines.append(f"Correlation: {context.correlation_id}")

    text = "\n".join(lines)

    blocks: List[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{title}*"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Resumo*\n{summary}"},
                {"type": "mrkdwn", "text": f"*Prioridade*\n{context.priority or '-'}"},
                {"type": "mrkdwn", "text": f"*Categoria*\n{context.category or '-'}"},
            ],
        },
    ]

    if details:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Detalhes*\n{details}"},
            }
        )
    if context.ticket_id:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Ticket `{context.ticket_id}`"},
                ],
            }
        )
    if context.links:
        link_text = " | ".join(context.links[:3])
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Links: {link_text}"},
                ],
            }
        )
    blocks.append(
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Correlation: {context.correlation_id}"},
                {"type": "mrkdwn", "text": f"Solicitado por: {context.requested_by or 'n/d'}"},
            ],
        }
    )

    return SlackMessage(channel=context.channel, text=text, blocks=blocks)
