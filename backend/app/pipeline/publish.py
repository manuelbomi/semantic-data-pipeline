"""
Stage 5: publish.

The last stop in the pipeline. Takes the fully enriched event, writes it
into the semantic layer store (so GET /api/entities/* has something to
return), records it in the trace store (so the event stream view can show
the full raw -> ... -> enriched journey), and pushes both out over the
WebSocket so the dashboard updates without polling.
"""
from __future__ import annotations

from app.models import EnrichedEvent
from app.semantic_layer.store import SemanticLayerStore
from app.semantic_layer.trace_store import TraceStore
from app.ws import ConnectionManager


async def publish(
    enriched: EnrichedEvent,
    store: SemanticLayerStore,
    traces: TraceStore,
    connections: ConnectionManager,
) -> None:
    traces.record_enriched(enriched)
    state = store.apply_enriched_event(enriched)

    await connections.broadcast(
        "event",
        {
            "event_id": enriched.event_id,
            "source": enriched.source,
            "kind": enriched.kind,
            "entity_ref": enriched.entity_ref,
            "canonical_id": enriched.canonical_id,
            "fields": enriched.fields,
        },
    )

    if state is not None:
        await connections.broadcast("entity_update", state.to_public_dict())
