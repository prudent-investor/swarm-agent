from __future__ import annotations

from typing import Any, Dict

from .metrics import GuardrailMetrics


def build_diagnostics(payload: Dict[str, Any], metrics: GuardrailMetrics) -> Dict[str, Any]:
    return {
        "normalized_text": payload.get("normalized_text", ""),
        "masked_preview": payload.get("masked_preview"),
        "flags": payload.get("flags", {}),
        "detected_injections": payload.get("detected_injections", []),
        "mode": payload.get("mode"),
        "metrics_snapshot": metrics.as_dict(),
    }