import statistics
from typing import List, Dict

from .models import PredictionRecord


def compute_error_rate(records: List[PredictionRecord]) -> float:
    labeled = [r for r in records if r.outcome is not None]
    if not labeled:
        return 0.0
    errors = sum(1 for r in labeled if round(r.prediction) != round(r.outcome))
    return errors / len(labeled)


def compute_latency_stats(records: List[PredictionRecord]) -> Dict[str, float]:
    if not records:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0}
    latencies = sorted(r.latency_ms for r in records)
    n = len(latencies)
    return {
        "p50": latencies[int(n * 0.50)],
        "p95": latencies[min(int(n * 0.95), n - 1)],
        "mean": round(statistics.mean(latencies), 2),
    }
