"""
LLM Adapter — uniform interface for deep signal analysis.

Toggle via MODEL_PATH environment variable:
    MODEL_PATH=mock  (default) → MockLLMAnalyzer backed by lexicon rules
    MODEL_PATH=/path/to/weights → real model loader (not yet implemented)

The MockLLMAnalyzer returns the same LLMAnalysis shape a fine-tuned Claude
or DistilBERT model would, so the pipeline is end-to-end testable without
any model weights.
"""

import os
from dataclasses import dataclass


@dataclass
class LLMAnalysis:
    intent: str
    topics: list[str]
    urgency_score: float  # 0.0 (calm) → 1.0 (critical)
    suggested_action: str
    confidence: float  # 0.0 → 1.0
    raw_response: str | None = None  # JSON string from real model; None for mock


_TOPIC_MAP: list[tuple[list[str], str]] = [
    (["password", "reset", "forgot"], "password_management"),
    (["login", "sign in", "log in", "access", "inlog"], "account_access"),
    (["payment", "charge", "refund", "billing", "invoice", "betaling"], "billing"),
    (["cancel", "subscription", "terminate", "kanselleer"], "subscription"),
    (
        ["popia", "gdpr", "personal data", "my data", "right of access", "section 23"],
        "data_privacy",
    ),
    (["slow", "timeout", "outage", "down", "unavailable", "503", "500"], "performance"),
    (["report", "dashboard", "export", "chart", "analytics"], "reporting"),
    (["api", "webhook", "integration", "sync", "zapier"], "integration"),
    (["setup", "onboard", "register", "sign up", "signup"], "onboarding"),
    (["mfa", "2fa", "two-factor", "otp", "authenticator"], "mfa"),
]

_URGENCY_KEYWORDS = {
    "immediately",
    "urgent",
    "asap",
    "critical",
    "emergency",
    "cannot work",
    "blocked",
    "completely",
    "unacceptable",
    "furious",
    "demand",
    "dringend",
}

_INTENT_RULES: list[tuple[list[str], str]] = [
    (["cancel", "terminate", "kanselleer", "end my subscription"], "cancellation"),
    (
        ["popia", "personal data", "right of access", "my data", "section 23", "delete my data"],
        "data_access_request",
    ),
    (["refund", "money back", "reimburse"], "refund_request"),
    (["great", "excellent", "thank", "amazing", "love", "lekker", "sharp"], "praise"),
    (["how do i", "can you help", "what is", "where do i"], "question"),
    (["feature", "suggest", "would be great", "please add"], "feature_request"),
]

_ACTION_MAP = {
    "cancellation": "escalate_to_account_manager",
    "data_access_request": "route_to_compliance",
    "refund_request": "create_refund_ticket",
    "praise": "log_positive_signal",
    "question": "create_standard_ticket",
    "feature_request": "route_to_product_team",
}


class MockLLMAnalyzer:
    """
    Mimics the LLMAnalysis interface using keyword rules instead of model weights.
    Activated when MODEL_PATH env var is absent or set to 'mock'.
    Swap this class for a real model loader when Claude API key is available.
    """

    def analyze(self, text: str) -> LLMAnalysis:
        text_lower = text.lower()

        topics = [
            topic for keywords, topic in _TOPIC_MAP if any(kw in text_lower for kw in keywords)
        ] or ["general"]

        urgency_count = sum(1 for kw in _URGENCY_KEYWORDS if kw in text_lower)
        urgency_score = round(min(1.0, urgency_count * 0.25), 4)

        intent = self._infer_intent(text_lower)
        suggested_action = self._suggest_action(intent, urgency_score)

        base_confidence = 0.5 + len(topics) * 0.05 + urgency_count * 0.03
        confidence = round(min(0.85, base_confidence), 4)

        return LLMAnalysis(
            intent=intent,
            topics=topics,
            urgency_score=urgency_score,
            suggested_action=suggested_action,
            confidence=confidence,
        )

    def _infer_intent(self, text_lower: str) -> str:
        for keywords, intent in _INTENT_RULES:
            if any(kw in text_lower for kw in keywords):
                return intent
        return "complaint"

    def _suggest_action(self, intent: str, urgency_score: float) -> str:
        if intent in _ACTION_MAP:
            return _ACTION_MAP[intent]
        if urgency_score >= 0.5:
            return "escalate_to_support_lead"
        return "create_standard_ticket"


def get_analyzer() -> MockLLMAnalyzer:
    """
    Return the appropriate analyzer based on MODEL_PATH.
    Extend this function when real model weights become available.
    """
    model_path = os.environ.get("MODEL_PATH", "mock")
    if model_path == "mock":
        return MockLLMAnalyzer()
    raise NotImplementedError(
        f"Real model loading not yet implemented for MODEL_PATH={model_path!r}. "
        "Set MODEL_PATH=mock to use the lexicon-backed mock."
    )
