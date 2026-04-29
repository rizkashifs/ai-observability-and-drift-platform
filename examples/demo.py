"""
End-to-end demo: prediction monitoring + drift detection + alerting.

Run from the project root:
    python -m examples.demo
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
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


def main():
    clear_store()
    model_id = "fraud-detector-v1"

    print("=== Step 1: Ingest baseline traffic (normal behavior) ===")
    baseline_events = [
        make_event("e1", model_id, {"amount": 100.0, "hour": 10.0, "risk": 0.2}, 0.0, 40.0, 0.0),
        make_event("e2", model_id, {"amount": 150.0, "hour": 11.0, "risk": 0.3}, 0.0, 45.0, 0.0),
        make_event("e3", model_id, {"amount": 200.0, "hour": 12.0, "risk": 0.1}, 0.0, 38.0, 0.0),
        make_event("e4", model_id, {"amount": 130.0, "hour": 14.0, "risk": 0.2}, 1.0, 50.0, 0.0),
        make_event("e5", model_id, {"amount": 180.0, "hour": 9.0,  "risk": 0.4}, 0.0, 42.0, 0.0),
    ]
    for ev in baseline_events:
        ingest_event(ev)

    baseline_records = get_records(model_id)
    baseline = build_baseline(model_id, baseline_records)
    print(f"  Built baseline from {baseline.sample_count} records")
    print(f"  Feature means: {baseline.feature_means}")

    print("\n=== Step 2: Ingest drifted traffic (amount and risk shifted) ===")
    clear_store()
    drifted_events = [
        make_event("d1", model_id, {"amount": 4000.0, "hour": 2.0, "risk": 0.95}, 0.0, 800.0, 1.0),
        make_event("d2", model_id, {"amount": 5500.0, "hour": 3.0, "risk": 0.98}, 0.0, 750.0, 1.0),
        make_event("d3", model_id, {"amount": 3200.0, "hour": 1.0, "risk": 0.90}, 0.0, 900.0, 1.0),
    ]
    for ev in drifted_events:
        ingest_event(ev)

    current_records = get_records(model_id)

    print("\n=== Step 3: Compute metrics ===")
    error_rate = compute_error_rate(current_records)
    latency = compute_latency_stats(current_records)
    print(f"  Error rate:   {error_rate:.0%}")
    print(f"  Latency p95:  {latency['p95']} ms")
    print(f"  Latency mean: {latency['mean']} ms")

    print("\n=== Step 4: Drift analysis ===")
    report = compute_drift(current_records, baseline)
    print(f"  Overall drift score: {report.overall_drift_score}")
    print(f"  Drifted features:    {report.drifted_features}")
    print(f"  Feature z-scores:    {report.drift_scores}")

    print("\n=== Step 5: Alert evaluation ===")
    policies = [
        AlertPolicy(policy_id="p1", metric="error_rate",  threshold=0.05, operator="gt", channel="slack"),
        AlertPolicy(policy_id="p2", metric="latency_p95", threshold=500.0, operator="gt", channel="slack"),
        AlertPolicy(policy_id="p3", metric="drift_score",  threshold=2.0,  operator="gt", channel="pagerduty"),
    ]
    metrics = {
        "error_rate":  error_rate,
        "latency_p95": latency["p95"],
        "drift_score": report.overall_drift_score,
    }
    fired = evaluate_policies(metrics, policies)
    if fired:
        print(f"  {len(fired)} alert(s) fired:")
        for alert in fired:
            print(f"    [{alert.policy_id}] {alert.metric} = {alert.value:.3f} (threshold {alert.threshold})")
    else:
        print("  No alerts fired.")


if __name__ == "__main__":
    main()
