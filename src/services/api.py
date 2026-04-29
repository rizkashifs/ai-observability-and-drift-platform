from fastapi import FastAPI, HTTPException
from typing import List, Optional
import uuid
from datetime import datetime, timezone

from ..core.models import TelemetryEvent, AlertPolicy, DriftReport
from ..core.metrics import compute_error_rate, compute_latency_stats
from ..pipelines.ingestion import ingest_event, get_records, clear_store
from ..pipelines.drift import build_baseline, compute_drift
from ..services.alerting import evaluate_policies

app = FastAPI(title="AI Observability Platform")

_baseline = None
_alert_policies: List[AlertPolicy] = [
    AlertPolicy(policy_id="p1", metric="error_rate", threshold=0.05, operator="gt", channel="slack"),
    AlertPolicy(policy_id="p2", metric="latency_p95", threshold=500.0, operator="gt", channel="slack"),
    AlertPolicy(policy_id="p3", metric="drift_score", threshold=2.0, operator="gt", channel="pagerduty"),
]


@app.post("/telemetry", summary="Ingest a telemetry event")
def post_telemetry(event: TelemetryEvent):
    record = ingest_event(event)
    return {"status": "ok", "stored": record is not None}


@app.get("/metrics", summary="Get aggregated metrics for a model")
def get_metrics(model_id: Optional[str] = None):
    records = get_records(model_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records found")
    latency = compute_latency_stats(records)
    return {
        "model_id": model_id or "all",
        "record_count": len(records),
        "error_rate": compute_error_rate(records),
        "latency_p50_ms": latency["p50"],
        "latency_p95_ms": latency["p95"],
        "latency_mean_ms": latency["mean"],
    }


@app.post("/baseline/build", summary="Build a baseline from current records")
def post_build_baseline(model_id: str):
    global _baseline
    records = get_records(model_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records found for this model")
    _baseline = build_baseline(model_id, records)
    return {"status": "baseline built", "sample_count": _baseline.sample_count}


@app.get("/drift", summary="Compare current records against the baseline")
def get_drift(model_id: str) -> DriftReport:
    if _baseline is None:
        raise HTTPException(status_code=400, detail="No baseline built yet. POST /baseline/build first.")
    records = get_records(model_id)
    return compute_drift(records, _baseline)


@app.get("/alerts", summary="Evaluate alert policies against current metrics")
def get_alerts(model_id: Optional[str] = None):
    records = get_records(model_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records found")
    latency = compute_latency_stats(records)
    drift_score = 0.0
    if _baseline:
        report = compute_drift(records, _baseline)
        drift_score = report.overall_drift_score
    metrics = {
        "error_rate": compute_error_rate(records),
        "latency_p95": latency["p95"],
        "drift_score": drift_score,
    }
    fired = evaluate_policies(metrics, _alert_policies)
    return {"metrics": metrics, "alerts": fired}


@app.delete("/store", summary="Clear all ingested records (for testing)")
def delete_store():
    clear_store()
    return {"status": "cleared"}
