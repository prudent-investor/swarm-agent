from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.settings import settings

from .anti_injection import cleanse_injection
from .diagnostics import build_diagnostics
from .metrics import GuardrailMetricsStore
from .moderation import moderate_text
from .normalizer import normalise_text
from .pii import mask_text
from .violations import (
    GuardrailViolation,
    detect_policy_violations,
    violations_from_pii_reasons,
)
from .validator import validate_payload


@dataclass
class PreprocessResult:
    message: str
    masked_for_log: str
    flags: Dict[str, object]
    detected_injections: List[str] = field(default_factory=list)
    violations: List[GuardrailViolation] = field(default_factory=list)
    latency_ms: float = 0.0

    def masked_preview(self, limit: int = 200) -> str:
        return self.masked_for_log[:limit]


@dataclass
class PostprocessResult:
    content: str
    flags: Dict[str, object]
    latency_ms: float = 0.0


class GuardrailsService:
    def __init__(self) -> None:
        self._metrics = GuardrailMetricsStore()

    def preprocess_input(
        self,
        *,
        message: str,
        user_id: Optional[str],
        metadata: Optional[Dict[str, object]],
        origin: str,
    ) -> PreprocessResult:
        start = time.perf_counter()
        validate_payload(message, user_id, metadata)
        self._metrics.increment("inputs_total")

        flags: Dict[str, object] = {
            "accents_stripped": False,
            "injection_detected": False,
            "pii_masked": False,
        }
        detected_injections: List[str] = []
        violations: List[GuardrailViolation] = []
        processed = message

        if settings.guardrails_enabled:
            processed, stripped = normalise_text(processed)
            flags["accents_stripped"] = stripped
            if stripped:
                self._metrics.increment("accents_stripped_total")

            if settings.guardrails_anti_injection_enabled:
                processed, detected, detected_injections = cleanse_injection(processed)
                processed = " ".join(processed.split())
                flags["injection_detected"] = detected
                if detected:
                    self._metrics.increment("injection_detected_total")
                    violations.append(
                        GuardrailViolation(
                            category="prompt_injection",
                            trigger=", ".join(detected_injections) or "prompt_injection",
                            description="Detected an attempt to override system instructions.",
                        )
                    )
        else:
            processed = message.strip()

        masked_for_log, masked_flag, mask_reasons = mask_text(processed)
        if masked_flag:
            flags["pii_masked"] = True
            self._metrics.increment("pii_masked_total")
            violations.extend(violations_from_pii_reasons(mask_reasons))

        violations.extend(detect_policy_violations(processed))
        violations = _unique_violations(violations)
        if violations:
            flags["violations"] = True
            flags["violations_details"] = [violation.as_dict() for violation in violations]
            flags["violation_categories"] = sorted({violation.category for violation in violations})

        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        return PreprocessResult(
            message=processed,
            masked_for_log=masked_for_log.strip(),
            flags=flags,
            detected_injections=detected_injections,
            violations=violations,
            latency_ms=latency_ms,
        )

    def filter_context(self, chunks):
        if not settings.guardrails_enabled or not settings.guardrails_anti_injection_enabled:
            return chunks
        filtered = []
        for chunk in chunks:
            text = getattr(chunk, "text", None)
            if text is None and isinstance(chunk, dict):
                text = chunk.get("text", "")
            text = text or ""
            _, detected, _ = cleanse_injection(text)
            if detected:
                self._metrics.increment("context_filtered_total")
                continue
            filtered.append(chunk)
        return filtered

    def postprocess_output(self, content: str) -> PostprocessResult:
        start = time.perf_counter()
        flags: Dict[str, object] = {
            "moderation_blocked": False,
            "output_truncated": False,
            "pii_masked_response": False,
        }
        processed = content

        if settings.guardrails_enabled:
            processed, blocked, moderation_reason = moderate_text(processed)
            if blocked:
                flags["moderation_blocked"] = True
                flags["moderation_reason"] = moderation_reason
                self._metrics.increment("moderation_blocked_total")

        masked_content, masked_flag, mask_reasons = mask_text(processed)
        if masked_flag:
            flags["pii_masked_response"] = True
            self._metrics.increment("pii_masked_total")
            if mask_reasons:
                flags["pii_masked_response_reasons"] = mask_reasons
        processed = masked_content

        max_chars = settings.guardrails_max_output_chars
        if max_chars and len(processed) > max_chars:
            processed = processed[: max_chars - 3].rstrip() + "..."
            flags["output_truncated"] = True
            self._metrics.increment("outputs_truncated_total")

        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        return PostprocessResult(content=processed, flags=flags, latency_ms=latency_ms)

    def diagnostics(self, query: str) -> Dict[str, object]:
        preprocess = self.preprocess_input(message=query, user_id=None, metadata=None, origin="diagnostics")
        metrics_snapshot = self._metrics.snapshot()
        masked_normalised, _, _ = mask_text(preprocess.message)
        payload = {
            "normalized_text": masked_normalised[: settings.guardrails_max_input_chars],
            "flags": preprocess.flags,
            "detected_injections": preprocess.detected_injections,
            "violations": [violation.as_dict() for violation in preprocess.violations],
            "masked_preview": preprocess.masked_preview(),
            "mode": settings.guardrails_mode,
        }
        return build_diagnostics(payload, metrics_snapshot)

    def metrics_snapshot(self) -> Dict[str, int]:
        return self._metrics.snapshot().as_dict()


def _unique_violations(violations: List[GuardrailViolation]) -> List[GuardrailViolation]:
    unique: List[GuardrailViolation] = []
    seen: set[tuple[str, str]] = set()
    for violation in violations:
        key = (violation.category, violation.trigger)
        if key in seen:
            continue
        seen.add(key)
        unique.append(violation)
    return unique


_guardrails_service: Optional[GuardrailsService] = None


def get_guardrails_service() -> GuardrailsService:
    global _guardrails_service
    if _guardrails_service is None:
        _guardrails_service = GuardrailsService()
    return _guardrails_service
