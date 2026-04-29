import statistics
from datetime import datetime, timezone
from typing import List

from ..core.models import PredictionRecord, Baseline, DriftReport


def build_baseline(model_id: str, records: List[PredictionRecord]) -> Baseline:
    if not records:
        raise ValueError("Cannot build baseline from empty records")
    features = list(records[0].features.keys())
    means, stds = {}, {}
    for feature in features:
        values = [r.features[feature] for r in records]
        means[feature] = statistics.mean(values)
        stds[feature] = statistics.stdev(values) if len(values) > 1 else 0.0
    timestamps = [r.timestamp for r in records]
    return Baseline(
        model_id=model_id,
        window_start=min(timestamps),
        window_end=max(timestamps),
        feature_means=means,
        feature_stds=stds,
        sample_count=len(records),
    )


def compute_drift(
    current: List[PredictionRecord],
    baseline: Baseline,
    z_threshold: float = 2.0,
) -> DriftReport:
    drift_scores = {}
    for feature, base_mean in baseline.feature_means.items():
        values = [r.features.get(feature, 0.0) for r in current]
        if not values:
            drift_scores[feature] = 0.0
            continue
        current_mean = statistics.mean(values)
        std = baseline.feature_stds.get(feature) or 1.0
        drift_scores[feature] = round(abs(current_mean - base_mean) / std, 3)

    drifted = [f for f, z in drift_scores.items() if z > z_threshold]
    overall = max(drift_scores.values(), default=0.0)

    return DriftReport(
        model_id=baseline.model_id,
        compared_at=datetime.now(timezone.utc),
        drifted_features=drifted,
        drift_scores=drift_scores,
        overall_drift_score=round(overall, 3),
    )
