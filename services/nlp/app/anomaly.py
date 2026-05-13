from dataclasses import dataclass


@dataclass
class AnomalyResult:
    sigma: float
    is_anomaly: bool
    recommended_action: str
    topic: str
    count: int


class AnomalyDetector:
    """Statistical spike detector using z-score (σ) against a rolling baseline."""

    def check_spike(
        self,
        topic: str,
        count: int,
        baseline_mean: float,
        baseline_std: float,
    ) -> AnomalyResult:
        if baseline_std == 0:
            sigma = float("inf") if count > baseline_mean else 0.0
        else:
            sigma = (count - baseline_mean) / baseline_std

        is_anomaly = sigma > 3.0

        if sigma >= 10.0:
            action = "escalate_to_product"
        elif sigma >= 5.0:
            action = "escalate_to_engineering"
        elif sigma >= 3.0:
            action = "notify_team_lead"
        else:
            action = "monitor"

        return AnomalyResult(
            sigma=round(sigma, 2),
            is_anomaly=is_anomaly,
            recommended_action=action,
            topic=topic,
            count=count,
        )
