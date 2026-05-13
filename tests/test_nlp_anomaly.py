"""
Anomaly Detector Tests
-----------------------
Validates the statistical spike detector (z-score / σ).
No external dependencies — pure Python arithmetic.
"""

import pytest

from services.nlp.app.anomaly import AnomalyDetector, AnomalyResult


@pytest.fixture(scope="module")
def detector():
    return AnomalyDetector()


# ---------------------------------------------------------------------------
# Sigma calculation
# ---------------------------------------------------------------------------


def test_spike_above_3sigma_detected(detector):
    result = detector.check_spike(
        topic="PasswordReset", count=45, baseline_mean=5.0, baseline_std=3.0
    )
    assert result.sigma > 3.0
    assert result.is_anomaly is True


def test_normal_count_not_anomaly(detector):
    result = detector.check_spike(
        topic="PasswordReset", count=6, baseline_mean=5.0, baseline_std=3.0
    )
    assert result.sigma <= 3.0
    assert result.is_anomaly is False


def test_sigma_calculation_correct(detector):
    result = detector.check_spike(
        topic="LoginFail", count=20, baseline_mean=5.0, baseline_std=5.0
    )
    assert abs(result.sigma - 3.0) < 0.01  # (20-5)/5 = 3.0


def test_exact_3sigma_not_anomaly(detector):
    result = detector.check_spike(
        topic="LoginFail", count=20, baseline_mean=5.0, baseline_std=5.0
    )
    assert result.is_anomaly is False  # > 3.0 required, not >= 3.0


def test_zero_std_with_spike_is_anomaly(detector):
    result = detector.check_spike(
        topic="Outage", count=10, baseline_mean=0.0, baseline_std=0.0
    )
    assert result.is_anomaly is True


def test_zero_std_no_spike_not_anomaly(detector):
    result = detector.check_spike(
        topic="Outage", count=0, baseline_mean=0.0, baseline_std=0.0
    )
    assert result.is_anomaly is False


# ---------------------------------------------------------------------------
# Recommended action tiers
# ---------------------------------------------------------------------------


def test_13sigma_escalates_to_product(detector):
    result = detector.check_spike(
        topic="PasswordReset", count=45, baseline_mean=5.0, baseline_std=3.0
    )
    assert result.recommended_action == "escalate_to_product"


def test_5sigma_escalates_to_engineering(detector):
    result = detector.check_spike(
        topic="LoginFail", count=30, baseline_mean=5.0, baseline_std=5.0
    )
    assert result.recommended_action == "escalate_to_engineering"


def test_3_5sigma_notifies_team_lead(detector):
    result = detector.check_spike(
        topic="AccountLocked", count=22, baseline_mean=5.0, baseline_std=5.0
    )
    assert result.recommended_action == "notify_team_lead"


def test_below_threshold_monitors(detector):
    result = detector.check_spike(
        topic="PasswordReset", count=7, baseline_mean=5.0, baseline_std=3.0
    )
    assert result.recommended_action == "monitor"


# ---------------------------------------------------------------------------
# Return type and metadata
# ---------------------------------------------------------------------------


def test_returns_anomaly_result_dataclass(detector):
    result = detector.check_spike(
        topic="LoginFail", count=10, baseline_mean=5.0, baseline_std=2.0
    )
    assert isinstance(result, AnomalyResult)


def test_result_carries_topic_and_count(detector):
    result = detector.check_spike(
        topic="PasswordReset", count=45, baseline_mean=5.0, baseline_std=3.0
    )
    assert result.topic == "PasswordReset"
    assert result.count == 45
