import time

from app.models import NormalizedEvent
from app.pipeline.entity_link import link_entity


def _normalized(entity_ref: str) -> NormalizedEvent:
    return NormalizedEvent(
        event_id="e1",
        source="test-source",
        kind="metric",
        entity_ref=entity_ref,
        fields={"cpu_pct": 10.0, "mem_pct": 10.0, "latency_ms": 10.0},
        stage_timestamps={"ingested_at": time.time(), "normalized_at": time.time()},
    )


def test_link_resolves_known_alias():
    out = link_entity(_normalized("USE1-WEB-01"))
    assert out.canonical_id == "host:use1-web-01"


def test_link_is_case_and_whitespace_insensitive():
    out = link_entity(_normalized("  use1-web-01  "))
    assert out.canonical_id == "host:use1-web-01"


def test_link_resolves_service_alias_variant():
    out = link_entity(_normalized("Checkout-Service"))
    assert out.canonical_id == "service:checkout"


def test_link_returns_none_for_unknown_entity():
    out = link_entity(_normalized("totally-unknown-host-99"))
    assert out.canonical_id is None
    # It should still carry the raw reference through, not drop it.
    assert out.entity_ref == "totally-unknown-host-99"


def test_link_records_stage_timestamp():
    out = link_entity(_normalized("use1-web-01"))
    assert "linked_at" in out.stage_timestamps
