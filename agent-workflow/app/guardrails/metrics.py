from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict


@dataclass
class GuardrailMetrics:
    inputs_total: int = 0
    accents_stripped_total: int = 0
    injection_detected_total: int = 0
    pii_masked_total: int = 0
    moderation_blocked_total: int = 0
    outputs_truncated_total: int = 0
    context_filtered_total: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "inputs_total": self.inputs_total,
            "accents_stripped_total": self.accents_stripped_total,
            "injection_detected_total": self.injection_detected_total,
            "pii_masked_total": self.pii_masked_total,
            "moderation_blocked_total": self.moderation_blocked_total,
            "outputs_truncated_total": self.outputs_truncated_total,
            "context_filtered_total": self.context_filtered_total,
        }


class GuardrailMetricsStore:
    def __init__(self) -> None:
        self._metrics = GuardrailMetrics()
        self._lock = Lock()

    def increment(self, field: str, value: int = 1) -> None:
        with self._lock:
            current = getattr(self._metrics, field, None)
            if current is None:
                raise AttributeError(f"Unknown metric field: {field}")
            setattr(self._metrics, field, current + value)

    def snapshot(self) -> GuardrailMetrics:
        with self._lock:
            return GuardrailMetrics(**self._metrics.as_dict())

    def reset(self) -> None:
        with self._lock:
            self._metrics = GuardrailMetrics()
