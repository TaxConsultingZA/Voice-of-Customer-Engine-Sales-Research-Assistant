"""
VoC NLP Pipeline — process_complaint() entry point.

Crisis Score governance:
    Green  Cs < 0.3   → fully automated, no human required
    Yellow 0.3–0.6    → automated with human notification
    Red    Cs ≥ 0.6   → strictly blocked, human approval required
"""

import math
from dataclasses import dataclass, field

from .anomaly import AnomalyDetector
from .sentiment import SentimentAnalyzer
from .slang import SlangPreprocessor
from .taxonomy import classify as classify_taxonomy

RED_THRESHOLD = 0.6
YELLOW_THRESHOLD = 0.3

_sentiment = SentimentAnalyzer()
_slang = SlangPreprocessor()
_anomaly = AnomalyDetector()

_INTENT_KEYWORDS: list[tuple[list[str], str]] = [
    (
        [
            "personal data",
            "my data",
            "right of access",
            "popia",
            "section 23",
            "delete my data",
            "persoonlike data",
        ],
        "data_access_request",
    ),
    (
        [
            "cancel",
            "cancellation",
            "terminate",
            "end my subscription",
            "kanselleer",
            "stop my subscription",
        ],
        "cancellation",
    ),
    (
        ["great", "excellent", "amazing", "love", "fantastic", "thank you", "lekker", "sharp"],
        "praise",
    ),
    (["how do i", "how can i", "what is", "where do i", "can you explain"], "question"),
    (["please add", "feature request", "would be great if", "suggest"], "request"),
]

_INTENT_MULTIPLIERS = {
    "cancellation": 1.3,
    "complaint": 1.1,
    "data_access_request": 0.8,
    "request": 0.6,
    "question": 0.4,
    "praise": 0.05,
    "unknown": 0.8,
}


@dataclass
class ComplaintResult:
    crisis_score: float
    escalation_triggered: bool
    actions: list = field(default_factory=list)
    at_risk_flag: bool = False
    taxonomy_path: str = ""
    intent: str = "complaint"
    routing: list = field(default_factory=list)
    requires_approval: bool = False
    sentiment_polarity: float = 0.0
    sentiment_confidence: float = 0.0
    language_detected: str = "en"
    contains_slang: bool = False
    anomaly_sigma: float | None = None
    anomaly_is_detected: bool = False
    anomaly_recommended_action: str | None = None


def _detect_intent(text: str) -> str:
    text_lower = text.lower()
    for keywords, intent in _INTENT_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return intent
    return "complaint"


def _detect_language(text: str) -> str:
    text_lower = text.lower()
    zulu_hints = {"ngiyacela", "ngiyabonga", "angikwazi", "akusebenzi", "kuhle"}
    xhosa_hints = {"ndicela", "enkosi", "andinako", "ayisebenzi", "ingxaki"}
    afrikaans_hints = {"asseblief", "dankie", "kan nie", "werk nie", "baie"}

    if any(token in text_lower for token in zulu_hints):
        return "zu"
    if any(token in text_lower for token in xhosa_hints):
        return "xh"
    if any(token in text_lower for token in afrikaans_hints):
        return "af"
    return "en"


def _compute_crisis_score(polarity: float, customer_arr: float, intent: str) -> float:
    # Severity: 0 = very positive, 1 = very negative
    severity = (1.0 - polarity) / 2.0

    # ARR factor: log scale normalised to R200K cap
    if customer_arr > 0:
        safe_arr = max(1.0, customer_arr)
        arr_factor = min(math.log10(safe_arr) / math.log10(200_000), 1.0)
    else:
        arr_factor = 0.1

    intent_factor = _INTENT_MULTIPLIERS.get(intent, 1.0)
    return round(max(0.0, min(severity * arr_factor * intent_factor, 1.0)), 4)


def process_complaint(complaint: dict) -> ComplaintResult:
    text = complaint.get("text", "")
    arr = float(complaint.get("customer_arr", 0))

    sentiment = _sentiment.analyze(text)
    intent = _detect_intent(text)
    language_detected = _detect_language(text)
    taxonomy_path = classify_taxonomy(text, intent)
    crisis_score = _compute_crisis_score(sentiment.polarity, arr, intent)
    anomaly_result = None

    anomaly_topic = complaint.get("anomaly_topic")
    anomaly_count = complaint.get("anomaly_count")
    anomaly_baseline_mean = complaint.get("anomaly_baseline_mean")
    anomaly_baseline_std = complaint.get("anomaly_baseline_std")

    if all(
        value is not None
        for value in (anomaly_topic, anomaly_count, anomaly_baseline_mean, anomaly_baseline_std)
    ):
        anomaly_result = _anomaly.check_spike(
            topic=str(anomaly_topic),
            count=int(anomaly_count),
            baseline_mean=float(anomaly_baseline_mean),
            baseline_std=float(anomaly_baseline_std),
        )

    escalation_triggered = crisis_score >= YELLOW_THRESHOLD
    at_risk_flag = crisis_score >= YELLOW_THRESHOLD or intent == "cancellation"
    requires_approval = crisis_score >= RED_THRESHOLD

    actions: list[str] = []
    routing: list[str] = []

    if intent == "data_access_request":
        actions.append("route_to_compliance")
        routing.append("popia_compliance_team")
    elif crisis_score >= RED_THRESHOLD:
        actions.append("human_review_required")
        actions.append("escalate_to_account_manager")
        routing.append("account_management")
    elif crisis_score >= YELLOW_THRESHOLD:
        actions.append("notify_customer_success")
        actions.append("create_priority_ticket")
        routing.append("customer_success")

    return ComplaintResult(
        crisis_score=crisis_score,
        escalation_triggered=escalation_triggered,
        actions=actions,
        at_risk_flag=at_risk_flag,
        taxonomy_path=taxonomy_path,
        intent=intent,
        routing=routing,
        requires_approval=requires_approval,
        sentiment_polarity=sentiment.polarity,
        sentiment_confidence=sentiment.confidence,
        language_detected=language_detected,
        contains_slang=_slang.contains_slang(text),
        anomaly_sigma=anomaly_result.sigma if anomaly_result else None,
        anomaly_is_detected=anomaly_result.is_anomaly if anomaly_result else False,
        anomaly_recommended_action=(anomaly_result.recommended_action if anomaly_result else None),
    )
