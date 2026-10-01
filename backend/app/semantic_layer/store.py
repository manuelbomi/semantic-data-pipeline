"""
The semantic layer itself: one consistent, current-state view per entity,
built up from whatever enriched events have flowed through the pipeline so
far.

This is the thing the rest of the JD description means by "a real-time,
highly reliable data substrate" - it's not the raw events, and it's not a
static asset table. It's "here is what we currently believe to be true
about this entity, and here's the evidence", kept up to date as new events
arrive.

Health is deliberately *not* stored as a fixed string that gets flipped by
whoever last touched the entity. It's computed from "how long ago was the
last bad signal", so an entity automatically goes back to healthy once
enough time passes without new problems, instead of staying stuck
"unhealthy" forever because nobody remembered to clear a flag.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from app.models import EnrichedEvent
from app.registry import CANONICAL_ENTITIES, entity_type

# How long a bad signal (high latency/cpu, a critical alert, an ERROR log)
# keeps an entity marked unhealthy before it's considered resolved.
UNHEALTHY_TTL_SECONDS = 20.0

_BAD_METRIC_CPU_PCT = 85.0
_BAD_METRIC_LATENCY_MS = 300.0
_BAD_ALERT_SEVERITIES = {"critical", "error"}
_BAD_LOG_SEVERITIES = {"ERROR"}


@dataclass
class EntityState:
    entity_id: str
    entity_type: str
    canonical_name: str
    dependency_context: dict[str, list[str]] = field(default_factory=lambda: {"depends_on": [], "depended_on_by": []})
    recent_deploys: list[dict] = field(default_factory=list)
    last_metric: dict | None = None
    last_bad_signal_at: float | None = None
    last_updated: float = field(default_factory=time.time)
    recent_events: deque = field(default_factory=lambda: deque(maxlen=20))

    def health(self, now: float | None = None) -> str:
        now = now if now is not None else time.time()
        if self.last_bad_signal_at is None:
            return "healthy"
        if now - self.last_bad_signal_at <= UNHEALTHY_TTL_SECONDS:
            return "unhealthy"
        return "healthy"

    def to_public_dict(self) -> dict:
        now = time.time()
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "canonical_name": self.canonical_name,
            "health": self.health(now),
            "last_updated": self.last_updated,
            "last_metric": self.last_metric,
            "dependency_context": self.dependency_context,
            "recent_deploys": self.recent_deploys,
            "recent_events": list(self.recent_events),
        }


def _is_bad_signal(kind: str, fields: dict) -> bool:
    if kind == "metric":
        return fields.get("cpu_pct", 0) > _BAD_METRIC_CPU_PCT or fields.get("latency_ms", 0) > _BAD_METRIC_LATENCY_MS
    if kind == "alert":
        return fields.get("severity") in _BAD_ALERT_SEVERITIES
    if kind == "log":
        return fields.get("severity") in _BAD_LOG_SEVERITIES
    return False


class SemanticLayerStore:
    """In-memory store, one process, one copy of the truth. A production
    version would back this with something like Redis or Postgres so
    multiple pipeline workers could share state - see the README.
    """

    def __init__(self) -> None:
        self._entities: dict[str, EntityState] = {}
        self.unresolved_count: int = 0

    def apply_enriched_event(self, event: EnrichedEvent) -> EntityState | None:
        if event.canonical_id is None:
            self.unresolved_count += 1
            return None

        state = self._entities.get(event.canonical_id)
        if state is None:
            aliases = CANONICAL_ENTITIES[event.canonical_id]["aliases"]
            state = EntityState(
                entity_id=event.canonical_id,
                entity_type=entity_type(event.canonical_id),
                canonical_name=aliases[0],
            )
            self._entities[event.canonical_id] = state

        now = time.time()
        state.dependency_context = event.dependency_context
        state.recent_deploys = event.recent_deploys
        state.last_updated = now
        if event.kind == "metric":
            state.last_metric = event.fields

        if _is_bad_signal(event.kind, event.fields):
            state.last_bad_signal_at = now

        state.recent_events.append(
            {
                "event_id": event.event_id,
                "source": event.source,
                "kind": event.kind,
                "fields": event.fields,
                "received_at": now,
            }
        )
        return state

    def get(self, entity_id: str) -> EntityState | None:
        return self._entities.get(entity_id)

    def all_states(self) -> list[EntityState]:
        return list(self._entities.values())

    def summary_list(self) -> list[dict]:
        now = time.time()
        return [
            {
                "entity_id": s.entity_id,
                "entity_type": s.entity_type,
                "canonical_name": s.canonical_name,
                "health": s.health(now),
                "last_updated": s.last_updated,
            }
            for s in self._entities.values()
        ]
