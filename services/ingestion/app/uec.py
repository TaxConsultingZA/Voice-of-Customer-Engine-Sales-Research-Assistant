import json
from pathlib import Path

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "uec_v1.json"


def load_uec_schema() -> dict:
    with _SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def validate_uec_event(event: dict) -> None:
    jsonschema.validate(instance=event, schema=load_uec_schema())
