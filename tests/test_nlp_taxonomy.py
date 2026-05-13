"""
Taxonomy Classifier Tests
--------------------------
Validates Signal Alpha domain classification (Authentication & Onboarding)
and broader taxonomy coverage. All tests are rule-based and run without a model.
"""

import pytest

from services.nlp.app.taxonomy import classify


# ---------------------------------------------------------------------------
# Signal Alpha — Authentication (highest priority)
# ---------------------------------------------------------------------------


def test_password_reset_classified_correctly():
    assert classify("The password reset email never arrives") == "Authentication.Login.PasswordReset"


def test_forgot_password_classified_correctly():
    assert classify("I clicked forgot password but nothing happened") == "Authentication.Login.PasswordReset"


def test_mfa_issue_classified_correctly():
    assert classify("The MFA code keeps expiring before I can enter it") == "Authentication.Login.MultiFactorAuth"


def test_two_factor_classified_correctly():
    assert classify("Two-factor authentication is not working") == "Authentication.Login.MultiFactorAuth"


def test_account_locked_classified_correctly():
    assert classify("My account is locked after too many attempts") == "Authentication.Login.AccountLocked"


def test_sso_failure_classified_correctly():
    assert classify("SSO login with our company account stopped working") == "Authentication.SSO.Failure"


def test_generic_login_failure_classified_correctly():
    assert classify("I cannot log in to my account") == "Authentication.Login.Failure"


def test_sign_in_failure_classified_correctly():
    assert classify("Cannot sign in, getting an error") == "Authentication.Login.Failure"


# ---------------------------------------------------------------------------
# Signal Alpha — Onboarding
# ---------------------------------------------------------------------------


def test_email_verification_classified_correctly():
    assert classify("My verification email never arrived") == "Onboarding.Registration.EmailVerification"


def test_signup_failure_classified_correctly():
    assert classify("I cannot complete my sign up, the form keeps failing") == "Onboarding.Registration.Failure"


def test_setup_wizard_classified_correctly():
    assert classify("The setup wizard crashes at step 3") == "Onboarding.Setup.Failure"


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


def test_popia_data_request_classified_correctly():
    assert classify("I want a copy of all personal data you hold about me") == "Compliance.Popia.DataAccessRequest"


def test_section_23_classified_correctly():
    assert classify("Section 23 right of access — please send me my data") == "Compliance.Popia.DataAccessRequest"


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------


def test_refund_request_classified_correctly():
    path = classify("I want a full refund for this month")
    assert path == "Billing.Payment.Refund"


def test_cancellation_classified_correctly():
    path = classify("Please cancel my subscription immediately")
    assert path == "Billing.Subscription.Cancellation"


def test_payment_failure_classified_correctly():
    path = classify("My payment keeps failing at checkout")
    assert path == "Billing.Payment.Failure"


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def test_unrecognised_text_returns_fallback():
    assert classify("I have a general enquiry") == "Support.General.Unknown"


# ---------------------------------------------------------------------------
# Taxonomy path format
# ---------------------------------------------------------------------------


def test_output_matches_uec_pattern():
    import re

    pattern = re.compile(r"^[A-Z][a-zA-Z0-9]+\.[A-Z][a-zA-Z0-9]+\.[A-Z][a-zA-Z0-9]+$")
    test_texts = [
        "Cannot log in",
        "Please refund my payment",
        "Setup wizard broken",
        "I want my personal data",
        "General question",
    ]
    for text in test_texts:
        path = classify(text)
        assert pattern.match(path), f"Path '{path}' does not match UEC format for: {text}"
