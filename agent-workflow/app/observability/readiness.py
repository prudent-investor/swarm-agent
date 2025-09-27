from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import importlib
from importlib import util

from app.settings import settings


@dataclass
class ReadinessStatus:
    ready: bool
    checks: Dict[str, Tuple[bool, str | None]]


_resource = importlib.import_module("resource") if util.find_spec("resource") else None
_psutil = importlib.import_module("psutil") if util.find_spec("psutil") else None


class ReadinessChecker:
    def __init__(self) -> None:
        self._index_dir = Path("data") / "rag" / "index"

    def evaluate(self) -> ReadinessStatus:
        checks: Dict[str, Tuple[bool, str | None]] = {}

        checks["openai_api_key"] = self._check_openai_key()
        checks["embeddings_store"] = self._check_embeddings_store()
        checks["system_resources"] = self._check_system_resources()

        ready = all(result for result, _ in checks.values())
        return ReadinessStatus(ready=ready, checks=checks)

    def _check_openai_key(self) -> Tuple[bool, str | None]:
        if settings.openai_api_key:
            return True, None
        return False, "OPENAI_API_KEY missing"

    def _check_embeddings_store(self) -> Tuple[bool, str | None]:
        if not settings.rag_enabled:
            return True, "rag_disabled"
        if self._index_dir.exists() and any(self._index_dir.glob("index_*.jsonl")):
            return True, None
        return False, f"missing embeddings index at {self._index_dir}"

    def _check_system_resources(self) -> Tuple[bool, str | None]:
        cpu_limit = settings.readiness_cpu_threshold
        mem_limit = settings.readiness_memory_threshold_mb

        cpu_ok, cpu_detail = _cpu_usage_ok(cpu_limit)
        mem_ok, mem_detail = _memory_usage_ok(mem_limit)

        if cpu_ok and mem_ok:
            return True, None

        detail_parts = []
        if not cpu_ok:
            detail_parts.append(cpu_detail)
        if not mem_ok:
            detail_parts.append(mem_detail)
        return False, "; ".join(part for part in detail_parts if part)


def _cpu_usage_ok(limit_percent: int) -> Tuple[bool, str | None]:
    try:
        load1, _, _ = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        usage_percent = (load1 / cpu_count) * 100
        return (usage_percent <= limit_percent, f"cpu_usage={usage_percent:.2f}")
    except (OSError, AttributeError):
        return True, "loadavg_unavailable"


def _memory_usage_ok(limit_mb: int) -> Tuple[bool, str | None]:
    if _resource is not None:
        usage = _resource.getrusage(_resource.RUSAGE_SELF)
        rss_kb = getattr(usage, "ru_maxrss", 0)
        used_mb = rss_kb / 1024 if os.name != "nt" else rss_kb / (1024 * 1024)
    elif _psutil is not None:
        process = _psutil.Process(os.getpid())
        used_mb = process.memory_info().rss / (1024 * 1024)
    else:
        return True, "memory_usage_unavailable"

    if used_mb <= limit_mb:
        return True, f"memory_used_mb={used_mb:.2f}"
    return False, f"memory_used_mb={used_mb:.2f}"


_checker: ReadinessChecker | None = None


def get_readiness_checker() -> ReadinessChecker:
    global _checker
    if _checker is None:
        _checker = ReadinessChecker()
    return _checker
