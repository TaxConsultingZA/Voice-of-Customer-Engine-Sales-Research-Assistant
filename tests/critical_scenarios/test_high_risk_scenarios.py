"""
Critical Scenario Test Suite
------------------------------
High-risk customer scenarios that validate the Decision Intelligence Engine's
Red/Yellow/Green governance gates.

All tests are currently skipped (Decision Intelligence Engine not yet built).
These are wired into CI so they activate automatically once F4 is integrated.
See SYSTEM_PROMPT §3.8 and §6 for governance thresholds.
"""

import pytest

RED_THRESHOLD = 0.6    # Crisis Score — requires human approval
YELLOW_THRESHOLD = 0.3  # Crisis Score — automation with notification


@pytest.mark.skip(reason="Requires Decision Intelligence Engine (F4) — activate post-integration")
def test_enterprise_login_failure_triggers_red():
    """
    R150K ARR customer unable to log in for 3 days → Crisis Score ≥ 0.6 (Red gate).
    Human approval required before any automated action.
    """
    from services.nlp.app.pipeline import process_complaint

    complaint = {
        "text": (
            "I've been trying to log in for 3 days. "
            "This is completely unacceptable! Cancel my account."
        ),
        "customer_arr": 150_000,
        "location": "Johannesburg",
        "channel": "email",
    }
    result = process_complaint(complaint)

    assert result.crisis_score >= RED_THRESHOLD, (
        f"Crisis score {result.crisis_score:.2f} below Red threshold {RED_THRESHOLD} "
        f"for R150K enterprise login failure"
    )
    assert result.escalation_triggered is True
    assert "human_review_required" in result.actions


@pytest.mark.skip(reason="Requires Decision Intelligence Engine (F4)")
def test_payment_failure_during_renewal_at_risk():
    """Payment processing error at renewal → account flagged as at-risk (Yellow+)."""
    from services.nlp.app.pipeline import process_complaint

    complaint = {
        "text": "My payment keeps failing and my subscription expires tomorrow. Please fix this!",
        "customer_arr": 85_000,
        "channel": "email",
    }
    result = process_complaint(complaint)

    assert result.at_risk_flag is True
    assert result.taxonomy_path.startswith("Billing.")
    assert result.crisis_score >= YELLOW_THRESHOLD


@pytest.mark.skip(reason="Requires POPIA compliance module")
def test_data_export_request_routes_to_compliance():
    """
    POPIA Section 23 right-of-access request must route to compliance team,
    not the standard CX queue.
    """
    from services.nlp.app.pipeline import process_complaint

    complaint = {
        "text": "I want a full copy of all personal data you hold about me.",
        "customer_arr": 12_000,
        "channel": "email",
    }
    result = process_complaint(complaint)

    assert result.intent == "data_access_request"
    assert "popia_compliance_team" in result.routing
    assert result.taxonomy_path == "Compliance.Popia.DataAccessRequest"


@pytest.mark.skip(reason="Requires Decision Intelligence Engine (F4)")
def test_enterprise_cancellation_requires_human_approval():
    """
    Cancellation intent on R200K ARR account → Red gate, human must approve
    before any automated response (no auto-refund, no auto-cancel).
    """
    from services.nlp.app.pipeline import process_complaint

    complaint = {
        "text": "Please cancel my subscription and refund my remaining months.",
        "customer_arr": 200_000,
        "channel": "email",
    }
    result = process_complaint(complaint)

    assert result.crisis_score >= RED_THRESHOLD
    assert result.requires_approval is True
    assert "auto_cancel" not in result.actions, (
        "Red gate violated: auto-cancel must not fire without human approval"
    )


@pytest.mark.skip(reason="Requires anomaly detection module")
def test_sentiment_spike_above_3sigma_flagged():
    """
    >3σ spike in negative mentions about PasswordReset triggers anomaly alert.
    Baseline: 5 mentions/week. Spike: 45 mentions in 7 days.
    """
    from services.nlp.app.anomaly import AnomalyDetector

    detector = AnomalyDetector()
    result = detector.check_spike(
        topic="PasswordReset",
        count=45,
        baseline_mean=5.0,
        baseline_std=3.0,
    )

    sigma = (45 - 5.0) / 3.0  # = 13.3σ
    assert result.sigma > 3.0, f"Anomaly detector returned σ={result.sigma:.1f}, expected >3.0"
    assert result.is_anomaly is True
    assert result.recommended_action == "escalate_to_product"


@pytest.mark.skip(reason="Requires Decision Intelligence Engine (F4)")
def test_smb_complaint_routes_yellow_not_red():
    """
    R15K ARR SMB customer complaint should be Yellow (0.3-0.6), not Red.
    Automated escalation allowed with notification — no human approval needed.
    """
    from services.nlp.app.pipeline import process_complaint

    complaint = {
        "text": "The dashboard export is not working. Please help.",
        "customer_arr": 15_000,
        "channel": "chat",
    }
    result = process_complaint(complaint)

    assert YELLOW_THRESHOLD <= result.crisis_score < RED_THRESHOLD, (
        f"Expected Yellow crisis score (0.3-0.6), got {result.crisis_score:.2f}"
    )
    assert result.requires_approval is False
