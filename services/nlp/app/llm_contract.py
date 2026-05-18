import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator


def _resolve_taxonomy_path() -> Path:
    env_dir = os.getenv("SCHEMAS_PATH")
    if env_dir:
        return Path(env_dir) / "taxonomy_v1.json"
    # Local dev: llm_contract.py lives at services/nlp/app/ — three levels inside repo root
    return Path(__file__).resolve().parents[3] / "schemas" / "taxonomy_v1.json"


_TAXONOMY_PATH = _resolve_taxonomy_path()


@lru_cache(maxsize=1)
def load_taxonomy_labels() -> set[str]:
    data = json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    labels: set[str] = set()
    for domain_name, domain_body in data.get("labels", {}).items():
        for capability_name, capability_body in domain_body.get("capabilities", {}).items():
            for theme_name in capability_body.get("themes", {}).keys():
                labels.add(f"{domain_name}.{capability_name}.{theme_name}")
    return labels


class TaxonomyLLMOutput(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sentiment_polarity: float = Field(..., ge=-1.0, le=1.0)
    at_risk_flag: bool
    reason_short: str = Field(..., min_length=3, max_length=240)
    language_detected: str = Field(default="en", min_length=2, max_length=10)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        allowed = load_taxonomy_labels()
        if value not in allowed:
            msg = f"Label '{value}' is not in taxonomy_v1.json allowed labels."
            raise ValueError(msg)
        return value


def parse_llm_output(raw_json: str) -> TaxonomyLLMOutput:
    """
    Parse and validate raw model JSON output into strict schema.
    Raises ValidationError when output is malformed.
    """
    try:
        return TaxonomyLLMOutput.model_validate_json(raw_json)
    except ValidationError:
        raise
