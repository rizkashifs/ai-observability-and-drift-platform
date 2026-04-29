from typing import List, Optional

from ..core.models import TelemetryEvent, PredictionRecord

_store: List[PredictionRecord] = []


def ingest_event(event: TelemetryEvent) -> Optional[PredictionRecord]:
    if event.event_type != "prediction":
        return None
    p = event.payload
    record = PredictionRecord(
        model_id=p["model_id"],
        timestamp=event.timestamp,
        features=p["features"],
        prediction=p["prediction"],
        latency_ms=p["latency_ms"],
        outcome=p.get("outcome"),
    )
    _store.append(record)
    return record


def get_records(model_id: Optional[str] = None) -> List[PredictionRecord]:
    if model_id:
        return [r for r in _store if r.model_id == model_id]
    return list(_store)


def clear_store() -> None:
    _store.clear()
