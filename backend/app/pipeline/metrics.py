"""
Pipeline health metrics, computed for real from observed timestamps.

Nothing in here is a fabricated or hard-coded number. Latency percentiles
come from actual stage_timestamps recorded as each event moves through the
pipeline; throughput comes from counting events in a trailing time window;
queue depth is read directly off the event bus.
"""
from __future__ import annotations

import statistics
import time
from collections import deque
from dataclasses import dataclass, field

# How many of the most recent latency samples / processed timestamps we
# keep per stage. Bounded so memory use doesn't grow forever.
_WINDOW = 500
# Throughput is "events processed in the last N seconds".
_THROUGHPUT_WINDOW_SECONDS = 10.0


@dataclass
class StageMetrics:
    name: str
    latencies_s: deque = field(default_factory=lambda: deque(maxlen=_WINDOW))
    processed_at: deque = field(default_factory=lambda: deque(maxlen=_WINDOW))
    processed_total: int = 0
    error_total: int = 0

    def record_success(self, latency_s: float) -> None:
        self.latencies_s.append(latency_s)
        self.processed_at.append(time.time())
        self.processed_total += 1

    def record_error(self) -> None:
        self.error_total += 1

    def throughput_per_sec(self) -> float:
        now = time.time()
        recent = [t for t in self.processed_at if now - t <= _THROUGHPUT_WINDOW_SECONDS]
        return round(len(recent) / _THROUGHPUT_WINDOW_SECONDS, 2)

    def latency_percentiles_ms(self) -> dict[str, float]:
        samples = list(self.latencies_s)
        if not samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        samples_ms = sorted(s * 1000 for s in samples)
        if len(samples_ms) < 2:
            only = round(samples_ms[0], 2)
            return {"p50": only, "p95": only, "p99": only}
        # statistics.quantiles needs n >= 2 samples, which we just checked.
        quantiles = statistics.quantiles(samples_ms, n=100, method="inclusive")
        return {
            "p50": round(quantiles[49], 2),
            "p95": round(quantiles[94], 2),
            "p99": round(quantiles[98], 2),
        }


class MetricsRegistry:
    """One StageMetrics per pipeline stage, plus whatever the event bus
    reports for queue depth. A single instance of this is shared across
    the whole app (see main.py).
    """

    def __init__(self, bus, stage_names: list[str], topic_by_stage: dict[str, str]) -> None:
        self._bus = bus
        self._topic_by_stage = topic_by_stage
        self.stages: dict[str, StageMetrics] = {name: StageMetrics(name) for name in stage_names}

    def record_success(self, stage: str, latency_s: float) -> None:
        self.stages[stage].record_success(latency_s)

    def record_error(self, stage: str) -> None:
        self.stages[stage].record_error()

    def snapshot(self) -> dict:
        out = {}
        for name, m in self.stages.items():
            out[name] = {
                "throughput_per_sec": m.throughput_per_sec(),
                "latency_ms": m.latency_percentiles_ms(),
                "processed_total": m.processed_total,
                "error_total": m.error_total,
                "queue_depth": self._bus.queue_depth(self._topic_by_stage[name]),
            }
        return out
