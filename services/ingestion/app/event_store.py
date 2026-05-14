import json
import os
from pathlib import Path

_DEFAULT_EVENT_LOG_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "processed" / "uec_events.jsonl"
)


def get_event_log_path() -> Path:
    return Path(os.getenv("INGESTION_EVENT_LOG_PATH", str(_DEFAULT_EVENT_LOG_PATH)))


def persist_event(event: dict) -> None:
    path = get_event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")
