from dataclasses import dataclass

from .slang import SlangPreprocessor

_NEGATIVE = {
    "broken",
    "fail",
    "failed",
    "failing",
    "error",
    "crash",
    "crashed",
    "bug",
    "issue",
    "problem",
    "cannot",
    "can't",
    "doesn't",
    "not working",
    "frustrated",
    "angry",
    "unacceptable",
    "useless",
    "terrible",
    "awful",
    "horrible",
    "hate",
    "disappointed",
    "locked",
    "expired",
    "invalid",
    "missing",
    "wrong",
    "slow",
    "never",
    "keeps failing",
    "completely broken",
    "no access",
    "still not",
    "unreliable",
    "unusable",
    "ridiculous",
}

_POSITIVE = {
    "great",
    "excellent",
    "amazing",
    "love",
    "perfect",
    "fantastic",
    "helpful",
    "resolved",
    "working",
    "fixed",
    "happy",
    "satisfied",
    "thank",
    "appreciate",
    "good",
    "awesome",
    "brilliant",
    "outstanding",
    "easy",
    "smooth",
    "fast",
    "reliable",
}

_STRONG_NEGATIVE = {
    "completely unacceptable",
    "absolutely terrible",
    "worst ever",
    "cancel my account",
    "demand a refund",
    "furious",
    "disgusting",
}


@dataclass
class SentimentResult:
    polarity: float  # -1.0 (most negative) → 1.0 (most positive)
    confidence: float  # 0.0 → 1.0
    label: str  # NEGATIVE | NEUTRAL | POSITIVE


class SentimentAnalyzer:
    """
    Lexicon-based SA-aware sentiment analyzer.
    Uses SA slang dictionary for polarity adjustment.
    Designed to be swapped for a fine-tuned DistilBERT model via
    environment variable MODEL_PATH when weights are available.
    """

    def __init__(self):
        self._slang = SlangPreprocessor()

    def analyze(self, text: str) -> SentimentResult:
        text_lower = text.lower()

        neg = sum(1 for kw in _NEGATIVE if kw in text_lower)
        pos = sum(1 for kw in _POSITIVE if kw in text_lower)
        strong_neg = sum(2 for kw in _STRONG_NEGATIVE if kw in text_lower)

        total_neg = neg + strong_neg
        slang_adj = self._slang.get_sentiment_adjustment(text)

        if total_neg > 0 or pos > 0:
            raw = (pos - total_neg) / (total_neg + pos + 2)
            polarity = max(-1.0, min(1.0, raw + slang_adj))
            confidence = min(0.95, 0.6 + abs(total_neg - pos) * 0.05)
        else:
            polarity = slang_adj
            confidence = 0.5 if slang_adj == 0 else 0.65

        if polarity < -0.1:
            label = "NEGATIVE"
        elif polarity > 0.1:
            label = "POSITIVE"
        else:
            label = "NEUTRAL"

        return SentimentResult(
            polarity=round(polarity, 4),
            confidence=round(confidence, 4),
            label=label,
        )
