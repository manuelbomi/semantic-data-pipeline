import time

from app.deploys import init_deploy_history
from app.models import LinkedEvent
from app.pipeline.enrich import enrich


def setup_module():
    # enrich() reads deploy history, so it needs to be seeded first, the
    # same way main.py seeds it on app startup.
    init_deploy_history()


def _linked(canonical_id: str | None) -> LinkedEvent:
    return LinkedEvent(
        event_id="e1",
        source="test-source",
        kind="metric",
        entity_ref="whatever",
        canonical_id=canonical_id,
        fields={"cpu_pct": 10.0, "mem_pct": 10.0, "latency_ms": 10.0},
        stage_timestamps={"ingested_at": time.time(), "normalized_at": time.time(), "linked_at": time.time()},
    )


def test_enrich_attaches_dependency_context_for_known_entity():
    out = enrich(_linked("service:checkout"))
    assert out.dependency_context["depends_on"] == ["service:payments", "service:inventory"]


def test_enrich_attaches_recent_deploy_for_checkout():
    # init_deploy_history() seeds a deploy for service:checkout 90s ago,
    # which falls inside the default recency window.
    out = enrich(_linked("service:checkout"))
    assert len(out.recent_deploys) == 1
    assert out.recent_deploys[0]["entity_id"] == "service:checkout"


def test_enrich_handles_unresolved_entity_gracefully():
    out = enrich(_linked(None))
    assert out.dependency_context == {"depends_on": [], "depended_on_by": []}
    assert out.recent_deploys == []


def test_enrich_records_stage_timestamp():
    out = enrich(_linked("service:payments"))
    assert "enriched_at" in out.stage_timestamps
