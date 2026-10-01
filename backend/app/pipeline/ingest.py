"""
The three simulated source feeds.

Each one plays the role of a real system you'd actually have in production:
a metrics agent, a log shipper, and an alerting system. They all describe
the same small fleet of hosts/services, but - on purpose - they each refer
to those hosts/services using a different naming convention. That mismatch
is not a bug; it's the reason entity_link.py has to exist at all.
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid

from app.models import RawEvent
from app.pipeline.event_bus import EventBus

# Aliases deliberately drawn from different "systems" so the same physical
# host/service shows up under different spellings depending on the source.
_METRIC_HOST_ALIASES = ["use1-web-01", "use1-web-02", "pay01.use1.internal", "i-0c3d4e5a"]
_LOG_SERVICE_ALIASES = ["Checkout-Service", "payments_svc", "inventory"]
_ALERT_ENTITY_ALIASES = ["USE1-WEB-01", "svc-payments", "use1-inv-01"]

# Which alias is "unhealthy" right now, cycling over time, so the dashboard
# has something interesting to show instead of a flat line of green.
_UNHEALTHY_ROTATION = ["use1-web-01", "pay01.use1.internal", None, None]


def _current_unhealthy_alias(now: float) -> str | None:
    """Rotate which host looks unhealthy every 45 seconds. This exists so a
    person watching the dashboard actually sees the agent react to
    something, instead of staring at permanently-healthy metrics.
    """
    slot = int(now // 45) % len(_UNHEALTHY_ROTATION)
    return _UNHEALTHY_ROTATION[slot]


async def metrics_source(bus: EventBus, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        now = time.time()
        alias = random.choice(_METRIC_HOST_ALIASES)
        unhealthy_alias = _current_unhealthy_alias(now)
        if alias == unhealthy_alias:
            cpu_pct = random.uniform(90, 99)
            latency_ms = random.uniform(320, 600)
        else:
            cpu_pct = random.uniform(10, 60)
            latency_ms = random.uniform(20, 150)

        event = RawEvent(
            event_id=str(uuid.uuid4()),
            source="metrics-agent",
            kind="metric",
            entity_ref=alias,
            payload={
                "cpu_pct": round(cpu_pct, 1),
                "mem_pct": round(random.uniform(30, 80), 1),
                "latency_ms": round(latency_ms, 1),
            },
            stage_timestamps={"ingested_at": now},
        )
        await bus.publish("raw", event)
        await asyncio.sleep(random.uniform(0.15, 0.35))


async def log_source(bus: EventBus, stop_event: asyncio.Event) -> None:
    messages = {
        "INFO": "request completed",
        "WARN": "retrying downstream call",
        "ERROR": "downstream call failed after 3 retries",
    }
    while not stop_event.is_set():
        now = time.time()
        alias = random.choice(_LOG_SERVICE_ALIASES)
        severity = random.choices(["INFO", "WARN", "ERROR"], weights=[75, 18, 7])[0]
        event = RawEvent(
            event_id=str(uuid.uuid4()),
            source="log-shipper",
            kind="log",
            entity_ref=alias,
            payload={"severity": severity, "message": messages[severity]},
            stage_timestamps={"ingested_at": now},
        )
        await bus.publish("raw", event)
        await asyncio.sleep(random.uniform(0.3, 0.6))


async def alert_source(bus: EventBus, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        now = time.time()
        unhealthy_alias = _current_unhealthy_alias(now)
        # Only fire a real alert while something is actually in the
        # "unhealthy" rotation slot - otherwise there's nothing to alert on.
        if unhealthy_alias is not None:
            # Map the unhealthy metric alias to its alert-system alias so
            # the same underlying host triggers both a metric spike and an
            # alert, under two different spellings.
            alert_alias = {
                "use1-web-01": "USE1-WEB-01",
                "pay01.use1.internal": "svc-payments",
            }.get(unhealthy_alias, random.choice(_ALERT_ENTITY_ALIASES))
            event = RawEvent(
                event_id=str(uuid.uuid4()),
                source="alert-system",
                kind="alert",
                entity_ref=alert_alias,
                payload={
                    "severity": "critical",
                    "metric": "latency_ms",
                    "threshold": 300,
                    "value": round(random.uniform(320, 600), 1),
                },
                stage_timestamps={"ingested_at": now},
            )
            await bus.publish("raw", event)
        await asyncio.sleep(random.uniform(4, 7))
