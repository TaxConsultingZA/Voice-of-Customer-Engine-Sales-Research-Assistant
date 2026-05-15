"""
LLM Adapter Tests — MockLLMAnalyzer
-------------------------------------
Validates that the mock adapter returns correct intents, topics, urgency scores,
suggested actions, and correct get_analyzer() behaviour. All tests run without
any model weights (lexicon-backed mock only).
"""

import os

from services.nlp.app.llm_adapter import LLMAnalysis, MockLLMAnalyzer, get_analyzer

# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_analyze_returns_llm_analysis():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I cannot log in to my account")
    assert isinstance(result, LLMAnalysis)


def test_all_fields_present():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("My payment keeps failing at checkout")
    assert hasattr(result, "intent")
    assert hasattr(result, "topics")
    assert hasattr(result, "urgency_score")
    assert hasattr(result, "suggested_action")
    assert hasattr(result, "confidence")


# ---------------------------------------------------------------------------
# Intent inference
# ---------------------------------------------------------------------------


def test_cancellation_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("Please cancel my subscription immediately")
    assert result.intent == "cancellation"


def test_afrikaans_cancellation_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("Kanselleer my intekening asseblief")
    assert result.intent == "cancellation"


def test_data_access_request_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I want a copy of all personal data you hold about me")
    assert result.intent == "data_access_request"


def test_popia_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("POPIA right of access request — send me my data")
    assert result.intent == "data_access_request"


def test_refund_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I want a full refund for this month's payment")
    assert result.intent == "refund_request"


def test_praise_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("The support team was amazing and resolved everything")
    assert result.intent == "praise"


def test_question_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("How do I reset my password?")
    assert result.intent == "question"


def test_default_complaint_intent():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("The dashboard is broken and showing errors")
    assert result.intent == "complaint"


# ---------------------------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------------------------


def test_billing_topic_detected():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("My payment keeps failing at checkout")
    assert "billing" in result.topics


def test_account_access_topic_detected():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I cannot log in to my account")
    assert "account_access" in result.topics


def test_subscription_topic_detected():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("Please cancel my subscription")
    assert "subscription" in result.topics


def test_data_privacy_topic_detected():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("POPIA right of access — send me my data")
    assert "data_privacy" in result.topics


def test_performance_topic_detected():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("The service is completely down and returning 503 errors")
    assert "performance" in result.topics


def test_multiple_topics_detected():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I cannot login and my payment failed")
    assert len(result.topics) >= 2


def test_unknown_text_returns_general_topic():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I have a general inquiry about your company")
    assert "general" in result.topics


# ---------------------------------------------------------------------------
# Urgency scoring
# ---------------------------------------------------------------------------


def test_urgent_text_has_high_urgency():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("This is completely unacceptable and urgent, I am blocked")
    assert result.urgency_score >= 0.5


def test_calm_text_has_low_urgency():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I have a question about invoices")
    assert result.urgency_score == 0.0


def test_urgency_score_within_bounds():
    analyzer = MockLLMAnalyzer()
    for text in [
        "URGENT CRITICAL EMERGENCY BLOCKED IMMEDIATELY",
        "Great product, love it",
        "The API keeps failing",
    ]:
        result = analyzer.analyze(text)
        assert 0.0 <= result.urgency_score <= 1.0, f"urgency out of bounds for: {text}"


# ---------------------------------------------------------------------------
# Suggested actions
# ---------------------------------------------------------------------------


def test_cancellation_suggests_escalate_to_account_manager():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("Please cancel my subscription")
    assert result.suggested_action == "escalate_to_account_manager"


def test_data_request_suggests_compliance():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I want a copy of my personal data")
    assert result.suggested_action == "route_to_compliance"


def test_refund_suggests_refund_ticket():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("I want a refund")
    assert result.suggested_action == "create_refund_ticket"


def test_praise_suggests_log_positive():
    analyzer = MockLLMAnalyzer()
    result = analyzer.analyze("This product is amazing, thank you!")
    assert result.suggested_action == "log_positive_signal"


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def test_confidence_within_bounds():
    analyzer = MockLLMAnalyzer()
    for text in ["I cannot log in", "refund please", "POPIA request", "general"]:
        result = analyzer.analyze(text)
        assert 0.0 <= result.confidence <= 1.0, f"confidence out of bounds for: {text}"


# ---------------------------------------------------------------------------
# get_analyzer() factory
# ---------------------------------------------------------------------------


def test_get_analyzer_returns_mock_by_default(monkeypatch):
    monkeypatch.delenv("MODEL_PATH", raising=False)
    analyzer = get_analyzer()
    assert isinstance(analyzer, MockLLMAnalyzer)


def test_get_analyzer_returns_mock_when_env_is_mock(monkeypatch):
    monkeypatch.setenv("MODEL_PATH", "mock")
    analyzer = get_analyzer()
    assert isinstance(analyzer, MockLLMAnalyzer)


def test_get_analyzer_raises_for_real_model_path(monkeypatch):
    monkeypatch.setenv("MODEL_PATH", "/models/distilbert-sa-v2.bin")
    try:
        get_analyzer()
        assert False, "Expected NotImplementedError"
    except NotImplementedError:
        pass
