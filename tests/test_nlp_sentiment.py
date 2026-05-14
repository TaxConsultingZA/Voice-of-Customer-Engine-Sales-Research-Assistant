"""
Sentiment Analyser Tests
------------------------
Validates the lexicon-based SA-aware sentiment analyser.
All tests run without a trained model — the baseline uses keyword + slang scoring.
"""

import pytest

from services.nlp.app.sentiment import SentimentAnalyzer, SentimentResult


@pytest.fixture(scope="module")
def analyser():
    return SentimentAnalyzer()


# ---------------------------------------------------------------------------
# Label classification
# ---------------------------------------------------------------------------


def test_negative_complaint_labelled_negative(analyser):
    result = analyser.analyze("I cannot log in and the login is completely broken")
    assert result.label == "NEGATIVE"
    assert result.polarity < 0


def test_positive_feedback_labelled_positive(analyser):
    result = analyser.analyze("The support team was excellent and resolved my issue")
    assert result.label == "POSITIVE"
    assert result.polarity > 0


def test_neutral_statement_labelled_neutral(analyser):
    result = analyser.analyze("I submitted a ticket yesterday")
    assert result.label == "NEUTRAL"


# ---------------------------------------------------------------------------
# Polarity range
# ---------------------------------------------------------------------------


def test_polarity_within_bounds(analyser):
    texts = [
        "Absolutely terrible, worst product ever, I hate it",
        "Amazing, brilliant, love this product, thank you",
        "The system processed my request",
    ]
    for text in texts:
        result = analyser.analyze(text)
        assert -1.0 <= result.polarity <= 1.0, f"Polarity out of bounds for: {text}"


def test_strong_negative_has_lower_polarity_than_mild_negative(analyser):
    strong = analyser.analyze("Cancel my account, this is completely unacceptable and I hate it")
    mild = analyser.analyze("The login is a bit slow sometimes")
    assert strong.polarity < mild.polarity


# ---------------------------------------------------------------------------
# SA slang adjustment
# ---------------------------------------------------------------------------


def test_eish_amplifies_negative(analyser):
    without = analyser.analyze("The login is broken")
    with_slang = analyser.analyze("Eish, the login is broken")
    assert with_slang.polarity <= without.polarity


def test_lekker_amplifies_positive(analyser):
    without = analyser.analyze("The feature works")
    with_slang = analyser.analyze("Lekker, the feature works")
    assert with_slang.polarity >= without.polarity


def test_kak_is_strong_negative_signal(analyser):
    result = analyser.analyze("This product is kak, it never works")
    assert result.label == "NEGATIVE"
    assert result.polarity < -0.1


def test_negated_positive_phrase_becomes_negative(analyser):
    result = analyser.analyze("This is not good and not reliable at all.")
    assert result.label == "NEGATIVE"


def test_afrikaans_negative_signal_detected(analyser):
    result = analyser.analyze("Die diens is baie sleg en dit werk nie.")
    assert result.label == "NEGATIVE"


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------


def test_confidence_within_bounds(analyser):
    result = analyser.analyze("Login fails every single time, completely broken")
    assert 0.0 <= result.confidence <= 1.0


def test_empty_like_text_returns_neutral_low_confidence(analyser):
    result = analyser.analyze("okay")
    assert result.confidence <= 0.65


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_sentiment_result_dataclass(analyser):
    result = analyser.analyze("My account is broken")
    assert isinstance(result, SentimentResult)
    assert hasattr(result, "polarity")
    assert hasattr(result, "confidence")
    assert hasattr(result, "label")
