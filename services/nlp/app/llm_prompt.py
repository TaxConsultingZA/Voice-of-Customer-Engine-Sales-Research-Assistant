import json
import os
from functools import lru_cache
from pathlib import Path

_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompts" / "taxonomy_classifier_v1.txt"


def _resolve_taxonomy_path() -> Path:
    env_dir = os.getenv("SCHEMAS_PATH")
    if env_dir:
        return Path(env_dir) / "taxonomy_v1.json"
    return Path(__file__).resolve().parents[3] / "schemas" / "taxonomy_v1.json"


_TAXONOMY_PATH = _resolve_taxonomy_path()


@lru_cache(maxsize=1)
def _taxonomy_entries() -> list[tuple[str, str]]:
    data = json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    entries: list[tuple[str, str]] = []
    for domain_name, domain_body in data.get("labels", {}).items():
        for capability_name, capability_body in domain_body.get("capabilities", {}).items():
            for theme_name, description in capability_body.get("themes", {}).items():
                entries.append((f"{domain_name}.{capability_name}.{theme_name}", str(description)))
    entries.sort(key=lambda x: x[0])
    return entries


def build_taxonomy_system_prompt(max_reason_chars: int = 240) -> str:
    template = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    entries = _taxonomy_entries()
    labels_block = "\n".join(f"- {label}: {description}" for label, description in entries)
    return (
        template.replace("{{LABEL_COUNT}}", str(len(entries)))
        .replace("{{ALLOWED_LABELS_BLOCK}}", labels_block)
        .replace("{{MAX_REASON_CHARS}}", str(max(max_reason_chars, 20)))
    )
