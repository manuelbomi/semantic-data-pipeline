"""
Stage 3: entity_link.

Resolves the event's raw entity_ref (whatever spelling the source system
happened to use) to a canonical entity id, using the registry in
app/registry.py. This is the entity-resolution step of the pipeline: it's
what lets "USE1-WEB-01", "use1-web-01" and "web01.use1.internal" all become
the same entity downstream.

Failing to resolve an alias is not treated as an error - it's a normal,
expected path (a new host that hasn't been added to the registry yet, or a
typo somewhere upstream). We still forward the event with canonical_id=None
so it's visible on the dashboard as "unresolved", instead of silently
dropping data on the floor.
"""
from __future__ import annotations

import time

from app.models import LinkedEvent, NormalizedEvent
from app.registry import resolve_alias


def link_entity(normalized: NormalizedEvent) -> LinkedEvent:
    canonical_id = resolve_alias(normalized.entity_ref)

    stage_timestamps = dict(normalized.stage_timestamps)
    stage_timestamps["linked_at"] = time.time()

    return LinkedEvent(
        event_id=normalized.event_id,
        source=normalized.source,
        kind=normalized.kind,
        entity_ref=normalized.entity_ref,
        canonical_id=canonical_id,
        fields=normalized.fields,
        stage_timestamps=stage_timestamps,
    )
