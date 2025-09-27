from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Iterable, Tuple

from app.settings import settings


_CHAT_LATENCY_BUCKETS: Tuple[float, ...] = (50.0, 100.0, 200.0, 500.0, 1000.0)
_MAX_CORRELATION_IDS = 128


@dataclass
class HistogramState:
    buckets: Dict[float, int]
    inf_count: int
    count: int
    total: float


class Histogram:
    def __init__(self, bucket_boundaries: Iterable[float]) -> None:
        buckets = [float(boundary) for boundary in bucket_boundaries]
        self._boundaries = tuple(sorted(buckets))
        self._state = HistogramState(
            buckets={boundary: 0 for boundary in self._boundaries},
            inf_count=0,
            count=0,
            total=0.0,
        )
        self._lock = Lock()
        self._per_correlation: "OrderedDict[str, HistogramState]" = OrderedDict()

    def observe(self, value: float, *, correlation_id: str | None = None) -> None:
        with self._lock:
            state = self._state
            state.count += 1
            state.total += value
            placed = False
            for boundary in self._boundaries:
                if value <= boundary:
                    state.buckets[boundary] += 1
                    placed = True
                    break
            if not placed:
                state.inf_count += 1

            if correlation_id:
                per_state = self._per_correlation.get(correlation_id)
                if per_state is None:
                    per_state = HistogramState(
                        buckets={boundary: 0 for boundary in self._boundaries},
                        inf_count=0,
                        count=0,
                        total=0.0,
                    )
                per_state.count += 1
                per_state.total += value
                placed_corr = False
                for boundary in self._boundaries:
                    if value <= boundary:
                        per_state.buckets[boundary] += 1
                        placed_corr = True
                        break
                if not placed_corr:
                    per_state.inf_count += 1
                self._per_correlation[correlation_id] = per_state
                self._enforce_correlation_limit()

    def snapshot(self) -> Tuple[HistogramState, "OrderedDict[str, HistogramState]"]:
        with self._lock:
            state_copy = HistogramState(
                buckets=dict(self._state.buckets),
                inf_count=self._state.inf_count,
                count=self._state.count,
                total=self._state.total,
            )
            per_copy: "OrderedDict[str, HistogramState]" = OrderedDict()
            for key, value in self._per_correlation.items():
                per_copy[key] = HistogramState(
                    buckets=dict(value.buckets),
                    inf_count=value.inf_count,
                    count=value.count,
                    total=value.total,
                )
            return state_copy, per_copy

    def reset(self) -> None:
        with self._lock:
            self._state = HistogramState(
                buckets={boundary: 0 for boundary in self._boundaries},
                inf_count=0,
                count=0,
                total=0.0,
            )
            self._per_correlation.clear()

    def _enforce_correlation_limit(self) -> None:
        while len(self._per_correlation) > _MAX_CORRELATION_IDS:
            self._per_correlation.popitem(last=False)


class MetricsRegistry:
    def __init__(self) -> None:
        self._chat_request_counters = defaultdict(int)
        self._redirect_total = 0
        self._lock = Lock()
        self._latency_histogram = Histogram(_CHAT_LATENCY_BUCKETS)

    def increment_chat_request(self, agent: str) -> None:
        if not settings.metrics_enabled:
            return
        with self._lock:
            self._chat_request_counters[agent] += 1

    def increment_redirect(self) -> None:
        if not settings.metrics_enabled:
            return
        with self._lock:
            self._redirect_total += 1

    def observe_latency(self, latency_ms: float, *, correlation_id: str | None = None) -> None:
        if not settings.metrics_enabled:
            return
        self._latency_histogram.observe(latency_ms, correlation_id=correlation_id)

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            counters = dict(self._chat_request_counters)
            redirect_total = self._redirect_total
        histogram, per_correlation = self._latency_histogram.snapshot()
        return {
            "chat_requests": counters,
            "redirect_total": redirect_total,
            "histogram": histogram,
            "histogram_per_corr": per_correlation,
        }

    def reset(self) -> None:
        with self._lock:
            self._chat_request_counters.clear()
            self._redirect_total = 0
        self._latency_histogram.reset()


_registry: MetricsRegistry | None = None


def get_metrics_registry() -> MetricsRegistry:
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


def format_prometheus_metrics() -> str:
    if not settings.metrics_enabled:
        return ""

    registry = get_metrics_registry()
    snapshot = registry.snapshot()
    lines = []

    lines.append("# HELP chat_requests_total Total chat requests by agent")
    lines.append("# TYPE chat_requests_total counter")
    chat_counters: Dict[str, int] = snapshot["chat_requests"]
    for agent in ("knowledge", "support", "custom", "slack"):
        value = chat_counters.get(agent, 0)
        lines.append(f'chat_requests_total{{agent="{agent}"}} {value}')

    lines.append("# HELP chat_redirect_total Total chat redirects to humans")
    lines.append("# TYPE chat_redirect_total counter")
    lines.append(f"chat_redirect_total {snapshot['redirect_total']}")

    guardrails_metrics = _guardrail_metrics_snapshot()
    guardrail_help = {
        "guardrails_accents_stripped_total": "Guardrails inputs that had accents stripped",
        "guardrails_injections_detected_total": "Guardrails inputs flagged for prompt injection",
        "guardrails_pii_masked_total": "Guardrails operations that masked PII",
        "guardrails_moderation_blocked_total": "Guardrails outputs blocked by moderation",
        "guardrails_outputs_truncated_total": "Guardrails outputs truncated by length limits",
    }
    for key, value in guardrails_metrics.items():
        metric_name = f"guardrails_{key}"
        lines.append(f"# HELP {metric_name} {guardrail_help.get(metric_name, 'Guardrails metric')}")
        lines.append(f"# TYPE {metric_name} counter")
        lines.append(f"{metric_name} {value}")

    lines.append("# HELP chat_request_latency_ms_bucket Histogram of chat request latency in milliseconds")
    lines.append("# TYPE chat_request_latency_ms_bucket histogram")
    histogram: HistogramState = snapshot["histogram"]
    cumulative = 0
    for boundary in _CHAT_LATENCY_BUCKETS:
        cumulative += histogram.buckets.get(boundary, 0)
        lines.append(
            f'chat_request_latency_ms_bucket{{le="{int(boundary)}"}} {cumulative}'
        )
    total_count = histogram.count
    lines.append('chat_request_latency_ms_bucket{le="+Inf"} ' + str(cumulative + histogram.inf_count))
    lines.append(f"chat_request_latency_ms_count {total_count}")
    lines.append(f"chat_request_latency_ms_sum {round(histogram.total, 6)}")

    per_corr: "OrderedDict[str, HistogramState]" = snapshot["histogram_per_corr"]
    for correlation_id, corr_state in per_corr.items():
        cumulative_corr = 0
        for boundary in _CHAT_LATENCY_BUCKETS:
            cumulative_corr += corr_state.buckets.get(boundary, 0)
            lines.append(
                f'chat_request_latency_ms_bucket{{le="{int(boundary)}", correlation_id="{correlation_id}"}} {cumulative_corr}'
            )
        lines.append(
            'chat_request_latency_ms_bucket{le="+Inf", correlation_id="%s"} %s'
            % (correlation_id, cumulative_corr + corr_state.inf_count)
        )
        lines.append(
            f'chat_request_latency_ms_count{{correlation_id="{correlation_id}"}} {corr_state.count}'
        )
        lines.append(
            f'chat_request_latency_ms_sum{{correlation_id="{correlation_id}"}} {round(corr_state.total, 6)}'
        )

    return "\n".join(lines) + "\n"


def _guardrail_metrics_snapshot() -> Dict[str, int]:
    try:
        from app.guardrails import get_guardrails_service

        service = get_guardrails_service()
        snapshot = service.metrics_snapshot()
        return {
            "accents_stripped_total": snapshot.get("accents_stripped_total", 0),
            "injections_detected_total": snapshot.get("injection_detected_total", 0),
            "pii_masked_total": snapshot.get("pii_masked_total", 0),
            "moderation_blocked_total": snapshot.get("moderation_blocked_total", 0),
            "outputs_truncated_total": snapshot.get("outputs_truncated_total", 0),
        }
    except Exception:  # pragma: no cover - defensive fallback if guardrails unavailable
        return {
            "accents_stripped_total": 0,
            "injections_detected_total": 0,
            "pii_masked_total": 0,
            "moderation_blocked_total": 0,
            "outputs_truncated_total": 0,
        }
