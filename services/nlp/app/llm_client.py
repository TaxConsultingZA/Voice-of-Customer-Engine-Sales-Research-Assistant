import os

import requests

from .llm_contract import TaxonomyLLMOutput, parse_llm_output
from .llm_prompt import build_taxonomy_system_prompt


class LLMClassifierError(Exception):
    """Raised when LLM classification call or parsing fails."""


def classify_complaint_with_llm(text: str) -> TaxonomyLLMOutput | None:
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return None

    model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
    timeout_seconds = float(os.getenv("CLAUDE_TIMEOUT_SECONDS", "20"))
    endpoint = os.getenv("CLAUDE_API_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
    system_prompt = build_taxonomy_system_prompt()

    body = {
        "model": model,
        "max_tokens": 350,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": f"Customer complaint text:\n{text}",
            }
        ],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        content = payload.get("content", [])
        text_parts = [
            str(block.get("text", "")).strip()
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        raw_output = "\n".join(part for part in text_parts if part)
        if not raw_output:
            raise LLMClassifierError("Claude returned empty output.")
        return parse_llm_output(raw_output)
    except Exception as exc:
        raise LLMClassifierError(f"Claude classification failed: {exc}") from exc
