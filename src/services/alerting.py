from datetime import datetime, timezone
from typing import List, Dict

from ..core.models import AlertPolicy, Alert


def evaluate_policies(metrics: Dict[str, float], policies: List[AlertPolicy]) -> List[Alert]:
    alerts = []
    for policy in policies:
        value = metrics.get(policy.metric)
        if value is None:
            continue
        fired = (
            (policy.operator == "gt" and value > policy.threshold)
            or (policy.operator == "lt" and value < policy.threshold)
        )
        if fired:
            alerts.append(Alert(
                policy_id=policy.policy_id,
                metric=policy.metric,
                value=value,
                threshold=policy.threshold,
                fired_at=datetime.now(timezone.utc),
            ))
    return alerts
