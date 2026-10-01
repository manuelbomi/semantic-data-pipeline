"""
Keeps the raw -> normalized -> linked -> enriched snapshot of recent events
around so the dashboard's event stream view can show exactly how one event
was transformed as it moved through the pipeline. This is purely for
visibility/debugging - the semantic layer itself (store.py) only cares
about the final enriched state, not the history of how each event got
there.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict
from typing import Any

_MAX_TRACES = 300


class TraceStore:
    def __init__(self) -> None:
        self._traces: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    def _get_or_create(self, event_id: str) -> dict[str, Any]:
        trace = self._traces.get(event_id)
        if trace is None:
            trace = {"event_id": event_id}
            self._traces[event_id] = trace
            self._traces.move_to_end(event_id)
            while len(self._traces) > _MAX_TRACES:
                self._traces.popitem(last=False)
        return trace

    def record_raw(self, raw) -> None:
        trace = self._get_or_create(raw.event_id)
        trace["raw"] = asdict(raw)

    def record_normalized(self, normalized) -> None:
        trace = self._get_or_create(normalized.event_id)
        trace["normalized"] = asdict(normalized)

    def record_linked(self, linked) -> None:
        trace = self._get_or_create(linked.event_id)
        trace["linked"] = asdict(linked)

    def record_enriched(self, enriched) -> None:
        trace = self._get_or_create(enriched.event_id)
        trace["enriched"] = asdict(enriched)
        self._traces.move_to_end(enriched.event_id)

    def get(self, event_id: str) -> dict[str, Any] | None:
        return self._traces.get(event_id)

    def recent_summaries(self, limit: int = 50) -> list[dict[str, Any]]:
        items = list(self._traces.values())[-limit:]
        items.reverse()  # newest first
        out = []
        for t in items:
            enriched = t.get("enriched")
            raw = t.get("raw")
            out.append(
                {
                    "event_id": t["event_id"],
                    "source": raw["source"] if raw else None,
                    "kind": raw["kind"] if raw else None,
                    "entity_ref": raw["entity_ref"] if raw else None,
                    "canonical_id": enriched["canonical_id"] if enriched else None,
                    "complete": enriched is not None,
                }
            )
        return out
