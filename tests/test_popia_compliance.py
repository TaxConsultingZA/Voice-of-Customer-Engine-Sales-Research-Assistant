"""
POPIA Compliance Tests
-----------------------
Validates that the Presidio-powered PII scanner correctly detects
South African PII at the THRESHOLD confidence level.

These tests run in CI and gate every pipeline merge.
Fail → build blocked, Data Protection Officer notified.
"""

import pytest

THRESHOLD = 0.85


@pytest.fixture(scope="module")
def analyzer():
    import os
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    model = os.getenv("SPACY_MODEL", "en_core_web_sm")
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": model}],
    })
    engine = AnalyzerEngine(nlp_engine=provider.create_engine())

    # Presidio's built-in phone recognizer misses SA +27 format with sm model.
    # A regex recognizer is more reliable for structured patterns anyway.
    sa_phone = PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        patterns=[
            Pattern("sa_intl", r"\+27[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}", score=0.9),
            Pattern("sa_local", r"\b0\d{2}[\s\-]?\d{3}[\s\-]?\d{4}\b", score=0.85),
        ],
    )
    engine.registry.add_recognizer(sa_phone)
    return engine


def pii_detected(analyzer, text: str) -> bool:
    results = analyzer.analyze(text=text, language="en", score_threshold=THRESHOLD)
    return len(results) > 0


# ---------------------------------------------------------------------------
# Must detect — these would violate POPIA if leaked
# ---------------------------------------------------------------------------


def test_email_address_detected(analyzer):
    assert pii_detected(analyzer, "Contact me at john.doe@company.co.za")


def test_phone_number_detected(analyzer):
    assert pii_detected(analyzer, "Call me on +27 82 123 4567")


def test_credit_card_detected(analyzer):
    assert pii_detected(analyzer, "My card number is 4111 1111 1111 1111")


def test_person_name_detected(analyzer):
    results = analyzer.analyze(
        text="Please help John Smith with his account", language="en", score_threshold=THRESHOLD
    )
    person_hits = [r for r in results if r.entity_type == "PERSON"]
    assert len(person_hits) > 0, "Person name not detected"


# ---------------------------------------------------------------------------
# Must NOT detect — false positives block the pipeline unnecessarily
# ---------------------------------------------------------------------------


def test_clean_product_complaint_no_false_positive(analyzer):
    """Generic product feedback must not trigger PII detection."""
    clean_text = (
        "The login feature is broken and I cannot access my dashboard. "
        "The password reset button does not send an email. Eish, very frustrating."
    )
    assert not pii_detected(analyzer, clean_text), (
        "False positive: PII detected in clean product complaint"
    )


def test_sa_slang_no_false_positive(analyzer):
    assert not pii_detected(
        analyzer, "Lekker work on the new feature, howzit with the dashboard update?"
    )


def test_taxonomy_path_no_false_positive(analyzer):
    assert not pii_detected(analyzer, "taxonomy_path: Authentication.Login.PasswordReset")


# ---------------------------------------------------------------------------
# Redaction integration
# ---------------------------------------------------------------------------


def test_redaction_removes_email(analyzer):
    from presidio_anonymizer import AnonymizerEngine
    anonymizer = AnonymizerEngine()

    text = "Please contact jane.smith@enterprise.co.za about this issue"
    results = analyzer.analyze(text=text, language="en", score_threshold=THRESHOLD)
    anonymised = anonymizer.anonymize(text=text, analyzer_results=results)

    assert "jane.smith@enterprise.co.za" not in anonymised.text
    assert len(anonymised.text) > 0  # text still exists, just redacted


def test_redaction_removes_phone(analyzer):
    from presidio_anonymizer import AnonymizerEngine
    anonymizer = AnonymizerEngine()

    text = "You can reach me on +27 11 456 7890 during business hours"
    results = analyzer.analyze(text=text, language="en", score_threshold=THRESHOLD)
    anonymised = anonymizer.anonymize(text=text, analyzer_results=results)

    assert "+27 11 456 7890" not in anonymised.text
