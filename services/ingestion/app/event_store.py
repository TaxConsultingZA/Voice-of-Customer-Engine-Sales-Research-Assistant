import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_event_log_path() -> Path:
    env = os.getenv("INGESTION_EVENT_LOG_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "data" / "processed" / "uec_events.jsonl"


def persist_event(event: dict) -> None:
    _persist_to_db(event)
    _persist_to_file(event)


def _persist_to_file(event: dict) -> None:
    path = get_event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")


def _persist_to_db(event: dict) -> None:
    from .db import get_db  # local import keeps tests that don't install psycopg2 working

    try:
        with get_db() as conn:
            if conn is None:
                return
            import psycopg2.extras

            sentiment = event.get("sentiment") or {}
            arr_linkage = event.get("arr_linkage") or {}
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO uec_events (
                        event_id, channel, event_timestamp, taxonomy_path, intent,
                        sentiment_polarity, sentiment_confidence,
                        customer_id, customer_arr, raw_text_hash, at_risk_flag, payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        event.get("event_id"),
                        event.get("channel"),
                        event.get("timestamp"),
                        event.get("taxonomy_path"),
                        event.get("intent"),
                        sentiment.get("polarity"),
                        sentiment.get("confidence"),
                        event.get("customer_id"),
                        arr_linkage.get("account_arr"),
                        event.get("raw_text_hash"),
                        bool(arr_linkage.get("at_risk_flag", False)),
                        psycopg2.extras.Json(event),
                    ),
                )
    except Exception as exc:
        logger.warning("PostgreSQL write failed for event %s: %s", event.get("event_id"), exc)
