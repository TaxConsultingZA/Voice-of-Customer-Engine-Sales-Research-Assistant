import json
import os
from datetime import UTC, datetime
from pathlib import Path

_DEFAULT_DEAD_LETTER_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "dead_letter" / "ingestion_failed_events.jsonl"
)


def get_dead_letter_path() -> Path:
    return Path(os.getenv("INGESTION_DEAD_LETTER_PATH", str(_DEFAULT_DEAD_LETTER_PATH)))


def write_dead_letter(source: str, payload: dict, reason: str) -> None:
    path = get_dead_letter_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": source,
        "reason": reason,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")
