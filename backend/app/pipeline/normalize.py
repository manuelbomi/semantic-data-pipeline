"""
Stage 2: normalize.

Takes whatever shape each source happens to use and puts it into one
consistent "fields" shape per event kind. This is boring on purpose - the
goal is that every stage after this one can assume a single schema per
event kind, instead of every consumer having to know about three sources'
worth of field-naming quirks.
"""
from __future__ import annotations

import time

from app.models import NormalizedEvent, RawEvent


def normalize(raw: RawEvent) -> NormalizedEvent:
    if raw.kind == "metric":
        fields = {
            "cpu_pct": float(raw.payload["cpu_pct"]),
            "mem_pct": float(raw.payload["mem_pct"]),
            "latency_ms": float(raw.payload["latency_ms"]),
        }
    elif raw.kind == "log":
        fields = {
            "severity": str(raw.payload["severity"]).upper(),
            "message": str(raw.payload["message"]),
        }
    elif raw.kind == "alert":
        fields = {
            "severity": str(raw.payload["severity"]).lower(),
            "metric": str(raw.payload["metric"]),
            "threshold": float(raw.payload["threshold"]),
            "value": float(raw.payload["value"]),
        }
    else:  # pragma: no cover - guarded by EventKind at the type level
        raise ValueError(f"unknown event kind: {raw.kind!r}")

    stage_timestamps = dict(raw.stage_timestamps)
    stage_timestamps["normalized_at"] = time.time()

    return NormalizedEvent(
        event_id=raw.event_id,
        source=raw.source,
        kind=raw.kind,
        entity_ref=raw.entity_ref,
        fields=fields,
        stage_timestamps=stage_timestamps,
    )
