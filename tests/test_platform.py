from datetime import datetime, timezone
import pytest

from src.core.models import TelemetryEvent, AlertPolicy
from src.core.metrics import compute_error_rate, compute_latency_stats
from src.pipelines.ingestion import ingest_event, get_records, clear_store
from src.pipelines.drift import build_baseline, compute_drift
from src.services.alerting import evaluate_policies


def make_event(event_id, model_id, features, prediction, latency_ms, outcome=None):
    return TelemetryEvent(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc),
        event_type="prediction",
        payload={
            "model_id": model_id,
            "features": features,
            "prediction": prediction,
            "latency_ms": latency_ms,
            "outcome": outcome,
        },
    )


@pytest.fixture(autouse=True)
def reset_store():
    clear_store()
    yield
    clear_store()


def test_ingest_prediction_event():
    ev = make_event("e1", "model-a", {"x": 1.0}, 0.0, 50.0)
    record = ingest_event(ev)
    assert record is not None
    assert record.model_id == "model-a"
    assert get_records("model-a") == [record]


def test_ingest_non_prediction_event_not_stored():
    ev = TelemetryEvent(
        event_id="e2",
        timestamp=datetime.now(timezone.utc),
        event_type="latency",
        payload={"info": "heartbeat"},
    )
    record = ingest_event(ev)
    assert record is None
    assert get_records() == []


def test_compute_error_rate():
    records = [
        make_event("e1", "m", {"x": 1.0}, 1.0, 10.0, outcome=1.0),
        make_event("e2", "m", {"x": 1.0}, 0.0, 10.0, outcome=1.0),  # error
        make_event("e3", "m", {"x": 1.0}, 0.0, 10.0, outcome=0.0),
    ]
    ingested = [ingest_event(e) for e in records]
    rate = compute_error_rate(ingested)
    assert abs(rate - 1 / 3) < 0.001


def test_compute_latency_stats():
    records = [
        make_event("e1", "m", {"x": 1.0}, 0.0, 100.0),
        make_event("e2", "m", {"x": 1.0}, 0.0, 200.0),
        make_event("e3", "m", {"x": 1.0}, 0.0, 300.0),
    ]
    ingested = [ingest_event(e) for e in records]
    stats = compute_latency_stats(ingested)
    assert stats["p50"] == 200.0
    assert stats["p95"] == 300.0


def test_build_baseline():
    events = [
        make_event("e1", "m", {"a": 1.0, "b": 2.0}, 0.0, 10.0),
        make_event("e2", "m", {"a": 3.0, "b": 4.0}, 0.0, 10.0),
    ]
    records = [ingest_event(e) for e in events]
    baseline = build_baseline("m", records)
    assert baseline.feature_means["a"] == 2.0
    assert baseline.feature_means["b"] == 3.0
    assert baseline.sample_count == 2


def test_drift_detected_when_mean_shifts():
    baseline_events = [
        make_event(f"b{i}", "m", {"amount": 100.0}, 0.0, 10.0) for i in range(5)
    ]
    baseline = build_baseline("m", [ingest_event(e) for e in baseline_events])

    clear_store()
    drifted_events = [
        make_event(f"d{i}", "m", {"amount": 9000.0}, 0.0, 10.0) for i in range(3)
    ]
    current = [ingest_event(e) for e in drifted_events]
    report = compute_drift(current, baseline)
    assert "amount" in report.drifted_features
    assert report.overall_drift_score > 2.0


def test_no_drift_when_distribution_stable():
    baseline_events = [
        make_event(f"b{i}", "m", {"amount": float(100 + i)}, 0.0, 10.0) for i in range(5)
    ]
    baseline = build_baseline("m", [ingest_event(e) for e in baseline_events])

    clear_store()
    stable_events = [
        make_event(f"s{i}", "m", {"amount": float(102 + i)}, 0.0, 10.0) for i in range(5)
    ]
    current = [ingest_event(e) for e in stable_events]
    report = compute_drift(current, baseline)
    assert "amount" not in report.drifted_features


def test_alert_fires_on_threshold_exceeded():
    policies = [
        AlertPolicy(policy_id="p1", metric="error_rate", threshold=0.05, operator="gt", channel="slack")
    ]
    alerts = evaluate_policies({"error_rate": 0.10}, policies)
    assert len(alerts) == 1
    assert alerts[0].policy_id == "p1"


def test_alert_does_not_fire_below_threshold():
    policies = [
        AlertPolicy(policy_id="p1", metric="error_rate", threshold=0.05, operator="gt", channel="slack")
    ]
    alerts = evaluate_policies({"error_rate": 0.02}, policies)
    assert alerts == []
