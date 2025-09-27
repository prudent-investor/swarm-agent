from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.settings import settings


_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    _RESERVED_KEYS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - override
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "route": getattr(record, "route", None),
            "agent": getattr(record, "agent", None),
            "latency_ms": getattr(record, "latency_ms", None),
            "flags": getattr(record, "flags", None),
        }

        for key, value in record.__dict__.items():
            if key in self._RESERVED_KEYS or key in payload:
                continue
            payload[key] = value

        if payload.get("flags") is None:
            payload["flags"] = {}

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        )

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    _CONFIGURED = True
