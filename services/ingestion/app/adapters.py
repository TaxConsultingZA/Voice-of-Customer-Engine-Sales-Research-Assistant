import hashlib
from datetime import UTC, datetime
from uuid import uuid4


def _as_utc_timestamp(value: str | None) -> str:
    if value:
        return value
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _hash_customer_id(raw_customer_id: str) -> str:
    return hashlib.sha256(raw_customer_id.encode("utf-8")).hexdigest()


def _default_taxonomy(text: str) -> str:
    text_lower = text.lower()
    if "password" in text_lower or "login" in text_lower or "log in" in text_lower:
        return "Authentication.Login.Failure"
    if "payment" in text_lower or "refund" in text_lower:
        return "Billing.Payment.Failure"
    return "Support.General.Unknown"


def _normalize_common(
    *,
    source: str,
    channel: str,
    text: str,
    raw_customer_id: str,
    timestamp: str | None = None,
    sentiment_polarity: float = 0.0,
    sentiment_confidence: float = 0.5,
    taxonomy_path: str | None = None,
) -> dict:
    if not text.strip():
        msg = f"{source} payload missing non-empty text field."
        raise ValueError(msg)
    if not raw_customer_id.strip():
        msg = f"{source} payload missing customer identifier."
        raise ValueError(msg)

    return {
        "event_id": str(uuid4()),
        "timestamp": _as_utc_timestamp(timestamp),
        "channel": channel,
        "customer_id": _hash_customer_id(raw_customer_id),
        "sentiment": {
            "polarity": sentiment_polarity,
            "confidence": sentiment_confidence,
        },
        "taxonomy_path": taxonomy_path or _default_taxonomy(text),
        "intent": "unknown",
    }


def normalize_email(payload: dict) -> dict:
    text = str(payload.get("text", payload.get("body", "")))
    raw_customer_id = str(payload.get("customer_id", payload.get("email_from", "")))
    return _normalize_common(
        source="email",
        channel="email",
        text=text,
        raw_customer_id=raw_customer_id,
        timestamp=payload.get("timestamp"),
        sentiment_polarity=float(payload.get("sentiment_polarity", 0.0)),
        sentiment_confidence=float(payload.get("sentiment_confidence", 0.5)),
        taxonomy_path=payload.get("taxonomy_path"),
    )


def normalize_whatsapp(payload: dict) -> dict:
    text = str(payload.get("message_text", payload.get("text", "")))
    raw_customer_id = str(payload.get("wa_id", payload.get("customer_id", "")))
    return _normalize_common(
        source="whatsapp",
        channel="whatsapp",
        text=text,
        raw_customer_id=raw_customer_id,
        timestamp=payload.get("timestamp"),
        sentiment_polarity=float(payload.get("sentiment_polarity", 0.0)),
        sentiment_confidence=float(payload.get("sentiment_confidence", 0.5)),
        taxonomy_path=payload.get("taxonomy_path"),
    )


def normalize_zendesk(payload: dict) -> dict:
    text = str(payload.get("description", payload.get("text", "")))
    raw_customer_id = str(payload.get("requester_id", payload.get("customer_id", "")))
    return _normalize_common(
        source="zendesk",
        channel="api",
        text=text,
        raw_customer_id=raw_customer_id,
        timestamp=payload.get("created_at"),
        sentiment_polarity=float(payload.get("sentiment_polarity", 0.0)),
        sentiment_confidence=float(payload.get("sentiment_confidence", 0.5)),
        taxonomy_path=payload.get("taxonomy_path"),
    )


NORMALIZERS = {
    "email": normalize_email,
    "whatsapp": normalize_whatsapp,
    "zendesk": normalize_zendesk,
}


def extract_text(source: str, payload: dict) -> str:
    if source == "email":
        return str(payload.get("text", payload.get("body", "")))
    if source == "whatsapp":
        return str(payload.get("message_text", payload.get("text", "")))
    if source == "zendesk":
        return str(payload.get("description", payload.get("text", "")))
    return ""


def extract_customer_arr(payload: dict) -> float:
    return float(payload.get("customer_arr", 0.0))
