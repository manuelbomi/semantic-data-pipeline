import time

from app.models import RawEvent
from app.pipeline.normalize import normalize


def _raw(kind: str, payload: dict, entity_ref: str = "use1-web-01") -> RawEvent:
    return RawEvent(
        event_id="e1",
        source="test-source",
        kind=kind,
        entity_ref=entity_ref,
        payload=payload,
        stage_timestamps={"ingested_at": time.time()},
    )


def test_normalize_metric_coerces_to_float():
    raw = _raw("metric", {"cpu_pct": "72.5", "mem_pct": 40, "latency_ms": 100})
    out = normalize(raw)
    assert out.fields == {"cpu_pct": 72.5, "mem_pct": 40.0, "latency_ms": 100.0}
    assert "normalized_at" in out.stage_timestamps
    assert "ingested_at" in out.stage_timestamps


def test_normalize_log_upper_cases_severity():
    raw = _raw("log", {"severity": "warn", "message": "retrying"})
    out = normalize(raw)
    assert out.fields["severity"] == "WARN"
    assert out.fields["message"] == "retrying"


def test_normalize_alert_lower_cases_severity():
    raw = _raw("alert", {"severity": "CRITICAL", "metric": "latency_ms", "threshold": 300, "value": 450})
    out = normalize(raw)
    assert out.fields["severity"] == "critical"
    assert out.fields["threshold"] == 300.0
    assert out.fields["value"] == 450.0


def test_normalize_preserves_event_identity():
    raw = _raw("metric", {"cpu_pct": 10, "mem_pct": 10, "latency_ms": 10})
    out = normalize(raw)
    assert out.event_id == raw.event_id
    assert out.source == raw.source
    assert out.entity_ref == raw.entity_ref
