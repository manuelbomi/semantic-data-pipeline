"""
Shared data shapes used across every pipeline stage.

We use plain dataclasses instead of Pydantic here because these objects get
created thousands of times a minute inside the pipeline's hot path, and
dataclasses are cheap. Pydantic models are used instead at the API boundary
(see semantic_layer/api.py and agent/api.py), where validation actually
matters because the data is leaving the process.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EventKind = Literal["metric", "log", "alert"]


@dataclass
class RawEvent:
    """What a source emits. entity_ref is deliberately messy/inconsistent -
    that's the whole point of this project. Downstream code is not allowed
    to trust it directly; it has to go through entity_link first.
    """

    event_id: str
    source: str
    kind: EventKind
    entity_ref: str
    payload: dict[str, Any]
    # stage_timestamps records when each stage touched this event (unix
    # epoch seconds). This is how we measure real per-stage latency instead
    # of making numbers up.
    stage_timestamps: dict[str, float] = field(default_factory=dict)


@dataclass
class NormalizedEvent:
    """RawEvent after normalize.py has put it into one consistent shape."""

    event_id: str
    source: str
    kind: EventKind
    entity_ref: str
    fields: dict[str, Any]
    stage_timestamps: dict[str, float]


@dataclass
class LinkedEvent:
    """NormalizedEvent after entity_link.py has resolved entity_ref to a
    canonical entity id. canonical_id is None when we could not resolve it -
    that is a normal, expected outcome, not an error.
    """

    event_id: str
    source: str
    kind: EventKind
    entity_ref: str
    canonical_id: str | None
    fields: dict[str, Any]
    stage_timestamps: dict[str, float]


@dataclass
class EnrichedEvent:
    """LinkedEvent after enrich.py has attached current context."""

    event_id: str
    source: str
    kind: EventKind
    entity_ref: str
    canonical_id: str | None
    fields: dict[str, Any]
    dependency_context: dict[str, list[str]]
    recent_deploys: list[dict[str, Any]]
    stage_timestamps: dict[str, float]


@dataclass
class Decision:
    """One decision produced by the agent, with its reasoning trace."""

    decision_id: str
    entity_id: str
    created_at: float
    action: str
    rule: str
    reasoning: str
    facts: dict[str, Any]
