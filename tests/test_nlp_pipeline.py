"""
NLP Pipeline Tests — process_complaint()
-----------------------------------------
Validates crisis score calculation, gate assignment, intent detection,
and routing logic. Tests run without a trained model.
"""

from services.nlp.app.pipeline import (
    RED_THRESHOLD,
    YELLOW_THRESHOLD,
    ComplaintResult,
    process_complaint,
)


def _complaint(text: str, arr: float = 0.0, channel: str = "email") -> dict:
    return {"text": text, "customer_arr": arr, "channel": channel}


# ---------------------------------------------------------------------------
# Crisis score — gate boundaries
# ---------------------------------------------------------------------------


def test_enterprise_login_failure_triggers_red():
    result = process_complaint(
        _complaint(
            "I cannot log in for 3 days, this is completely unacceptable. Cancel my account.",
            arr=150_000,
        )
    )
    assert result.crisis_score >= RED_THRESHOLD
    assert result.requires_approval is True
    assert "human_review_required" in result.actions


def test_enterprise_cancellation_triggers_red():
    result = process_complaint(
        _complaint(
            "Please cancel my subscription and refund my remaining months.",
            arr=200_000,
        )
    )
    assert result.crisis_score >= RED_THRESHOLD
    assert result.requires_approval is True
    assert "auto_cancel" not in result.actions


def test_mid_arr_complaint_is_yellow():
    result = process_complaint(_complaint("My payment keeps failing at checkout.", arr=85_000))
    assert result.crisis_score >= YELLOW_THRESHOLD
    assert result.at_risk_flag is True


def test_smb_complaint_is_yellow_not_red():
    result = process_complaint(
        _complaint("The dashboard export is not working. Please help.", arr=15_000)
    )
    assert YELLOW_THRESHOLD <= result.crisis_score < RED_THRESHOLD
    assert result.requires_approval is False


def test_positive_feedback_is_green():
    result = process_complaint(
        _complaint("The support team was amazing and resolved everything!", arr=50_000)
    )
    assert result.crisis_score < YELLOW_THRESHOLD
    assert result.requires_approval is False
    assert result.escalation_triggered is False


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------


def test_cancellation_intent_detected():
    result = process_complaint(_complaint("Please cancel my subscription immediately."))
    assert result.intent == "cancellation"


def test_data_access_request_intent_detected():
    result = process_complaint(_complaint("I want a copy of all personal data you hold about me."))
    assert result.intent == "data_access_request"


def test_data_access_request_routes_to_compliance():
    result = process_complaint(_complaint("POPIA right of access — please send me my data."))
    assert "popia_compliance_team" in result.routing
    assert "route_to_compliance" in result.actions


def test_complaint_intent_is_default():
    result = process_complaint(_complaint("The login page is broken."))
    assert result.intent == "complaint"


# ---------------------------------------------------------------------------
# Taxonomy classification via pipeline
# ---------------------------------------------------------------------------


def test_login_complaint_classified_to_authentication():
    result = process_complaint(_complaint("I cannot log in to my account."))
    assert result.taxonomy_path.startswith("Authentication.")


def test_payment_complaint_classified_to_billing():
    result = process_complaint(_complaint("My payment keeps failing at checkout."))
    assert result.taxonomy_path.startswith("Billing.")


def test_signup_complaint_classified_to_onboarding():
    result = process_complaint(_complaint("I cannot complete my sign up."))
    assert result.taxonomy_path.startswith("Onboarding.")


# ---------------------------------------------------------------------------
# SA slang detection
# ---------------------------------------------------------------------------


def test_eish_detected_as_slang():
    result = process_complaint(_complaint("Eish, the login is broken again!"))
    assert result.contains_slang is True


def test_clean_text_no_slang():
    result = process_complaint(_complaint("The login page is not working."))
    assert result.contains_slang is False


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_complaint_result_dataclass():
    result = process_complaint(_complaint("The system is slow."))
    assert isinstance(result, ComplaintResult)


def test_crisis_score_within_bounds():
    texts = [
        ("The login is completely broken and unacceptable", 200_000),
        ("Great product, love it!", 5_000),
        ("Dashboard export not working", 15_000),
    ]
    for text, arr in texts:
        result = process_complaint(_complaint(text, arr=arr))
        assert 0.0 <= result.crisis_score <= 1.0, f"Score out of bounds for: {text}"


def test_sub_unit_arr_does_not_create_negative_crisis_score():
    result = process_complaint(_complaint("The system is broken and terrible.", arr=0.5))
    assert result.crisis_score >= 0.0


def test_anomaly_inputs_are_processed_when_provided():
    result = process_complaint(
        {
            "text": "Password reset requests are suddenly exploding.",
            "customer_arr": 80_000,
            "anomaly_topic": "PasswordReset",
            "anomaly_count": 45,
            "anomaly_baseline_mean": 5.0,
            "anomaly_baseline_std": 3.0,
        }
    )
    assert result.anomaly_sigma is not None
    assert result.anomaly_is_detected is True
    assert result.anomaly_recommended_action == "escalate_to_product"
