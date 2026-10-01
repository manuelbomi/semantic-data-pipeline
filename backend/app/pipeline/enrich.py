"""
Stage 4: enrich.

Attaches context that a single raw event never carries on its own: what
this entity depends on, what depends on it, and whether it was deployed
recently. An agent (or a human) looking at "latency is high on checkout"
in isolation can't tell whether that's a brand new regression or a known
side effect of something upstream - the context is what makes the event
actually useful for a decision.

Events that didn't resolve to a canonical entity (canonical_id is None)
skip enrichment - there's no registry entry to pull context from - and pass
through with empty context so they still show up on the dashboard.
"""
from __future__ import annotations

import time

from app.deploys import recent_deploys_for
from app.models import EnrichedEvent, LinkedEvent
from app.registry import dependencies_of, dependents_of


def enrich(linked: LinkedEvent) -> EnrichedEvent:
    stage_timestamps = dict(linked.stage_timestamps)
    stage_timestamps["enriched_at"] = time.time()

    if linked.canonical_id is None:
        dependency_context: dict[str, list[str]] = {"depends_on": [], "depended_on_by": []}
        recent_deploys: list[dict] = []
    else:
        dependency_context = {
            "depends_on": dependencies_of(linked.canonical_id),
            "depended_on_by": dependents_of(linked.canonical_id),
        }
        recent_deploys = [
            {"entity_id": d.entity_id, "deployed_at": d.deployed_at, "version": d.version}
            for d in recent_deploys_for(linked.canonical_id)
        ]

    return EnrichedEvent(
        event_id=linked.event_id,
        source=linked.source,
        kind=linked.kind,
        entity_ref=linked.entity_ref,
        canonical_id=linked.canonical_id,
        fields=linked.fields,
        dependency_context=dependency_context,
        recent_deploys=recent_deploys,
        stage_timestamps=stage_timestamps,
    )
