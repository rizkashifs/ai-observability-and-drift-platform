from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime


class PredictionRecord(BaseModel):
    model_id: str
    timestamp: datetime
    features: Dict[str, float]
    prediction: float
    latency_ms: float
    outcome: Optional[float] = None  # actual label, filled in later


class TelemetryEvent(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: str  # "prediction", "error", "latency"
    payload: Dict[str, Any]


class Baseline(BaseModel):
    model_id: str
    window_start: datetime
    window_end: datetime
    feature_means: Dict[str, float]
    feature_stds: Dict[str, float]
    sample_count: int


class DriftReport(BaseModel):
    model_id: str
    compared_at: datetime
    drifted_features: List[str]
    drift_scores: Dict[str, float]  # feature -> z-score magnitude
    overall_drift_score: float


class AlertPolicy(BaseModel):
    policy_id: str
    metric: str       # "error_rate", "latency_p95", "drift_score"
    threshold: float
    operator: str     # "gt" or "lt"
    channel: str


class Alert(BaseModel):
    policy_id: str
    metric: str
    value: float
    threshold: float
    fired_at: datetime
