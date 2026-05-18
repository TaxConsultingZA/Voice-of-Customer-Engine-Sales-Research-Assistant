import json
import os
from datetime import UTC, datetime
from pathlib import Path

def get_dead_letter_path() -> Path:
    env = os.getenv("INGESTION_DEAD_LETTER_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "data" / "dead_letter" / "ingestion_failed_events.jsonl"


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
