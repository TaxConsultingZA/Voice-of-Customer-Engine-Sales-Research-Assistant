import json
import os
from pathlib import Path

import jsonschema


def _uec_schema_path() -> Path:
    schemas_dir = os.getenv("SCHEMAS_PATH")
    if schemas_dir:
        return Path(schemas_dir) / "uec_v1.json"
    return Path(__file__).resolve().parents[3] / "schemas" / "uec_v1.json"


def load_uec_schema() -> dict:
    with _uec_schema_path().open(encoding="utf-8") as f:
        return json.load(f)


def validate_uec_event(event: dict) -> None:
    jsonschema.validate(instance=event, schema=load_uec_schema())
