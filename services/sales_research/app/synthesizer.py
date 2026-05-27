"""
Claude-backed synthesizer that turns raw context into a validated SalesBrief.

Reuses the same HTTP pattern as services.nlp.app.llm_client so we don't
duplicate Claude config, retries, or error handling.

Anti-hallucination post-processing:
- Strict Pydantic validation against SalesBrief schema rejects malformed output.
- Citation post-filter drops any source_url not present in WEB_CONTEXT URLs.
- case_studies entries are dropped if their case_id is not in CASE_STUDY_CANDIDATES.
- After filtering, model_validator re-caps confidence to the new evidence count.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

from .contracts import SalesBrief
from .prompt_builder import build_system_prompt, build_user_message

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ENV_PATH)

_MAX_TOKENS = 2048
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


class SynthesizerError(Exception):
    """Raised when Claude output cannot be coerced into a valid SalesBrief."""


def synthesize_brief(
    company_name: str,
    web_context_blocks: list[dict],
    case_study_candidates: list[dict],
    icp_markdown: str | None = None,
) -> SalesBrief:
    """Run a single Claude call and return a validated, post-filtered SalesBrief."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise SynthesizerError(
            "CLAUDE_API_KEY is not set — cannot synthesize brief. "
            "Add it to .env or set NLP_CLASSIFIER_MODE=shadow for evaluation."
        )

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = float(os.getenv("CLAUDE_TIMEOUT_SECONDS", "30"))
    endpoint = os.getenv("CLAUDE_API_BASE_URL", "https://api.anthropic.com") + "/v1/messages"

    system_prompt = build_system_prompt(icp_markdown)
    user_message = build_user_message(company_name, web_context_blocks, case_study_candidates)

    body = {
        "model": model,
        "max_tokens": _MAX_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        resp = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        text_parts = [
            block["text"].strip()
            for block in payload.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        raw = "\n".join(p for p in text_parts if p)
    except Exception as exc:
        raise SynthesizerError(f"Claude API call failed: {exc}") from exc

    if not raw:
        raise SynthesizerError("Claude returned an empty response.")

    # Strip markdown fences if the model wrapped the JSON anyway.
    fenced = _FENCE_RE.fullmatch(raw.strip())
    if fenced:
        raw = fenced.group(1).strip()

    try:
        brief_dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SynthesizerError(
            f"Claude output is not valid JSON: {exc}\nFirst 500 chars: {raw[:500]}"
        ) from exc

    # Post-filter to enforce citation provenance and case_id integrity.
    allowed_urls = {doc.get("url", "").strip() for doc in web_context_blocks if doc.get("url")}
    allowed_case_ids = {
        c.get("case_id", "").strip() for c in case_study_candidates if c.get("case_id")
    }
    brief_dict = _post_filter(brief_dict, allowed_urls, allowed_case_ids)

    try:
        return SalesBrief.model_validate(brief_dict)
    except Exception as exc:
        raise SynthesizerError(f"SalesBrief validation failed after post-filter: {exc}") from exc


def _post_filter(
    raw: dict,
    allowed_urls: set[str],
    allowed_case_ids: set[str],
) -> dict:
    """Remove citations not backed by web context and case_ids not in candidates."""

    def filter_citations(citations: list[dict]) -> list[dict]:
        if not allowed_urls:
            return citations
        return [c for c in citations if c.get("source_url", "").strip() in allowed_urls]

    raw["snapshot_citations"] = filter_citations(raw.get("snapshot_citations") or [])
    raw["recent_signals"] = filter_citations(raw.get("recent_signals") or [])

    filtered_pains = []
    for pain in raw.get("pain_points") or []:
        pain["citations"] = filter_citations(pain.get("citations") or [])
        if pain["citations"]:
            filtered_pains.append(pain)
    raw["pain_points"] = filtered_pains

    if allowed_case_ids:
        raw["case_studies"] = [
            cs
            for cs in (raw.get("case_studies") or [])
            if cs.get("case_id", "").strip() in allowed_case_ids
        ]

    return raw
