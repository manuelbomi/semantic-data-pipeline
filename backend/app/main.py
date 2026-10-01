"""
Wires the whole thing together: starts the three ingest sources, the four
pipeline stage consumers, the agent's polling loop, a metrics broadcaster,
and exposes the REST + WebSocket API the dashboard talks to.

Nothing in here does real work itself - main.py is just plumbing. The
actual logic lives in pipeline/*.py, semantic_layer/*.py and agent/*.py,
each of which can be unit tested without booting this file at all.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.agent.decision_engine import DecisionEngine
from app.deploys import init_deploy_history
from app.models import EnrichedEvent, LinkedEvent, NormalizedEvent
from app.pipeline.enrich import enrich
from app.pipeline.entity_link import link_entity
from app.pipeline.event_bus import InProcessEventBus
from app.pipeline.ingest import alert_source, log_source, metrics_source
from app.pipeline.metrics import MetricsRegistry
from app.pipeline.normalize import normalize
from app.pipeline.publish import publish
from app.semantic_layer.store import SemanticLayerStore
from app.semantic_layer.trace_store import TraceStore
from app.ws import ConnectionManager

STAGE_TOPICS = {
    "normalize": "raw",
    "entity_link": "normalized",
    "enrich": "linked",
    "publish": "enriched",
}

AGENT_POLL_INTERVAL_SECONDS = 3.0
METRICS_BROADCAST_INTERVAL_SECONDS = 1.0


async def _normalize_loop(bus, traces, metrics, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        raw = await bus.get("raw")
        traces.record_raw(raw)
        try:
            normalized: NormalizedEvent = normalize(raw)
            traces.record_normalized(normalized)
            latency = normalized.stage_timestamps["normalized_at"] - normalized.stage_timestamps["ingested_at"]
            metrics.record_success("normalize", latency)
            await bus.publish("normalized", normalized)
        except Exception:
            metrics.record_error("normalize")


async def _entity_link_loop(bus, traces, metrics, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        normalized = await bus.get("normalized")
        try:
            linked: LinkedEvent = link_entity(normalized)
            traces.record_linked(linked)
            latency = linked.stage_timestamps["linked_at"] - linked.stage_timestamps["normalized_at"]
            metrics.record_success("entity_link", latency)
            await bus.publish("linked", linked)
        except Exception:
            metrics.record_error("entity_link")


async def _enrich_loop(bus, traces, metrics, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        linked = await bus.get("linked")
        try:
            enriched: EnrichedEvent = enrich(linked)
            traces.record_enriched(enriched)
            latency = enriched.stage_timestamps["enriched_at"] - enriched.stage_timestamps["linked_at"]
            metrics.record_success("enrich", latency)
            await bus.publish("enriched", enriched)
        except Exception:
            metrics.record_error("enrich")


async def _publish_loop(bus, store, traces, connections, metrics, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        enriched = await bus.get("enriched")
        try:
            await publish(enriched, store, traces, connections)
            latency = time.time() - enriched.stage_timestamps["enriched_at"]
            metrics.record_success("publish", latency)
        except Exception:
            metrics.record_error("publish")


async def _agent_loop(engine: DecisionEngine, connections: ConnectionManager, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await asyncio.sleep(AGENT_POLL_INTERVAL_SECONDS)
        for decision in engine.evaluate_all():
            await connections.broadcast(
                "decision",
                {
                    "decision_id": decision.decision_id,
                    "entity_id": decision.entity_id,
                    "created_at": decision.created_at,
                    "action": decision.action,
                    "rule": decision.rule,
                    "reasoning": decision.reasoning,
                    "facts": decision.facts,
                },
            )


async def _metrics_broadcast_loop(metrics: MetricsRegistry, connections: ConnectionManager, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await asyncio.sleep(METRICS_BROADCAST_INTERVAL_SECONDS)
        await connections.broadcast("metrics", metrics.snapshot())


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_deploy_history()

    bus = InProcessEventBus(maxsize=1000)
    store = SemanticLayerStore()
    traces = TraceStore()
    connections = ConnectionManager()
    metrics = MetricsRegistry(bus, stage_names=list(STAGE_TOPICS.keys()), topic_by_stage=STAGE_TOPICS)
    engine = DecisionEngine(store)
    stop_event = asyncio.Event()

    app.state.store = store
    app.state.traces = traces
    app.state.connections = connections
    app.state.metrics = metrics
    app.state.engine = engine

    tasks = [
        asyncio.create_task(metrics_source(bus, stop_event)),
        asyncio.create_task(log_source(bus, stop_event)),
        asyncio.create_task(alert_source(bus, stop_event)),
        asyncio.create_task(_normalize_loop(bus, traces, metrics, stop_event)),
        asyncio.create_task(_entity_link_loop(bus, traces, metrics, stop_event)),
        asyncio.create_task(_enrich_loop(bus, traces, metrics, stop_event)),
        asyncio.create_task(_publish_loop(bus, store, traces, connections, metrics, stop_event)),
        asyncio.create_task(_agent_loop(engine, connections, stop_event)),
        asyncio.create_task(_metrics_broadcast_loop(metrics, connections, stop_event)),
    ]

    try:
        yield
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="semantic-data-pipeline", lifespan=lifespan)

# Local dev only: the Vite dev server runs on a different port than
# uvicorn, so the browser needs CORS to let the dashboard call the API.
# A real deployment would lock this down to the dashboard's real origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/entities")
def list_entities():
    return app.state.store.summary_list()


@app.get("/api/entities/{entity_id}/state")
def entity_state(entity_id: str):
    state = app.state.store.get(entity_id)
    if state is None:
        raise HTTPException(status_code=404, detail="unknown entity")
    return state.to_public_dict()


@app.get("/api/metrics/pipeline")
def pipeline_metrics():
    return app.state.metrics.snapshot()


@app.get("/api/agent/decisions")
def agent_decisions(limit: int = 50):
    return app.state.engine.recent(limit=limit)


@app.get("/api/events/recent")
def recent_events(limit: int = 50):
    return app.state.traces.recent_summaries(limit=limit)


@app.get("/api/events/{event_id}/trace")
def event_trace(event_id: str):
    trace = app.state.traces.get(event_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="unknown event id")
    return trace


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await app.state.connections.connect(websocket)
    try:
        while True:
            # The dashboard doesn't send anything meaningful over this
            # socket - we still need to await recv() so we notice a
            # disconnect promptly instead of leaking the connection.
            await websocket.receive_text()
    except WebSocketDisconnect:
        app.state.connections.disconnect(websocket)
