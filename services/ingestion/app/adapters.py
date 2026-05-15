import hashlib
import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

_DEFAULT_FIELD_MAPPING_PATH = (
    Path(__file__).resolve().parents[3] / "schemas" / "field_mapping_v1.json"
)
_SOURCE_TO_CHANNEL = {
    "email": "email",
    "whatsapp": "whatsapp",
    "zendesk": "api",
    "web_form": "web_form",
    "api": "api",
}


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


def _mapping_path() -> Path:
    return Path(os.getenv("FIELD_MAPPING_PATH", str(_DEFAULT_FIELD_MAPPING_PATH)))


@lru_cache(maxsize=1)
def load_field_mapping() -> dict:
    with _mapping_path().open(encoding="utf-8") as f:
        return json.load(f)


def reload_field_mapping() -> dict:
    load_field_mapping.cache_clear()
    return load_field_mapping()


def _channel_field_map(source: str) -> dict:
    mapping = load_field_mapping()
    channels = mapping.get("channels", {})
    if source not in channels:
        msg = f"Unsupported source '{source}' in field mapping."
        raise ValueError(msg)
    return channels[source].get("field_map", {})


def _pick_first(payload: dict, aliases: list[str], default=None):
    for alias in aliases:
        value = payload.get(alias)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return default


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


def normalize_payload(source: str, payload: dict) -> dict:
    field_map = _channel_field_map(source)
    text = str(_pick_first(payload, field_map.get("text", []), ""))
    raw_customer_id = str(_pick_first(payload, field_map.get("customer_id", []), ""))
    timestamp = _pick_first(payload, field_map.get("timestamp", []), None)
    sentiment_polarity = _as_float(
        _pick_first(payload, field_map.get("sentiment_polarity", []), 0.0), 0.0
    )
    sentiment_confidence = _as_float(
        _pick_first(payload, field_map.get("sentiment_confidence", []), 0.5), 0.5
    )
    taxonomy_path = _pick_first(payload, field_map.get("taxonomy_path", []), None)

    channel = _SOURCE_TO_CHANNEL.get(source, source)
    return _normalize_common(
        source=source,
        channel=channel,
        text=text,
        raw_customer_id=raw_customer_id,
        timestamp=str(timestamp) if timestamp is not None else None,
        sentiment_polarity=sentiment_polarity,
        sentiment_confidence=sentiment_confidence,
        taxonomy_path=str(taxonomy_path) if taxonomy_path is not None else None,
    )


def normalize_email(payload: dict) -> dict:
    return normalize_payload("email", payload)


def normalize_whatsapp(payload: dict) -> dict:
    return normalize_payload("whatsapp", payload)


def normalize_zendesk(payload: dict) -> dict:
    return normalize_payload("zendesk", payload)


def normalize_web_form(payload: dict) -> dict:
    return normalize_payload("web_form", payload)


def normalize_api(payload: dict) -> dict:
    return normalize_payload("api", payload)


NORMALIZERS = {
    "email": normalize_email,
    "whatsapp": normalize_whatsapp,
    "zendesk": normalize_zendesk,
    "web_form": normalize_web_form,
    "api": normalize_api,
}


def extract_text(source: str, payload: dict) -> str:
    field_map = _channel_field_map(source)
    return str(_pick_first(payload, field_map.get("text", []), ""))


def extract_customer_arr(source: str, payload: dict) -> float:
    field_map = _channel_field_map(source)
    return _as_float(_pick_first(payload, field_map.get("customer_arr", []), 0.0), 0.0)
