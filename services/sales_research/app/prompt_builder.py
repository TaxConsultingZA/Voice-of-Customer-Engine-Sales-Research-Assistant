"""
Assemble the Claude system prompt + user message for the synthesizer.

The system prompt template lives in `prompts/sales_brief_v1.txt` with two
placeholders that get injected here at call time:
  {{SCHEMA_BLOCK}}  — the JSON schema as a string, so the model sees the
                       authoritative contract every call.
  {{ICP_BLOCK}}     — the live ICP markdown (per-tenant in the future).

Keeping schema + ICP in the prompt (rather than only in code) makes the
constraints visible to the model and trims hallucinations on edge cases.
"""

from __future__ import annotations

import json
from pathlib import Path

_PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "sales_brief_v1.txt"
_SCHEMA_FILE = Path(__file__).resolve().parents[3] / "schemas" / "sales_brief_v1.json"
_DEFAULT_ICP = (
    "Target customers: South African mid-market financial services, retail, and "
    "professional services firms (200–5,000 staff). Buying centre is CFO / Head "
    "of Compliance / Head of Engineering. Highest-priority pain themes: "
    "POPIA + SARB compliance reporting, fragile API integrations, and reconciliation "
    "errors caused by manual data flows."
)


def build_system_prompt(icp_markdown: str | None = None) -> str:
    """Return the fully-resolved system prompt for a single Claude call."""
    template = _PROMPT_FILE.read_text(encoding="utf-8")
    schema_json = json.dumps(json.loads(_SCHEMA_FILE.read_text(encoding="utf-8")), indent=2)
    icp = (icp_markdown or _DEFAULT_ICP).strip()
    return template.replace("{{SCHEMA_BLOCK}}", schema_json).replace("{{ICP_BLOCK}}", icp)


def build_user_message(
    company_name: str,
    web_context_blocks: list[dict],
    case_study_candidates: list[dict],
) -> str:
    """Render the user-message body the Claude API will receive.

    Format is plain Markdown — Claude handles structured text well.
    Each block is clearly fenced so the model can map citations back.
    """
    lines: list[str] = [f"TARGET COMPANY: {company_name}", ""]

    lines.append("WEB_CONTEXT:")
    if not web_context_blocks:
        lines.append("(no web context returned)")
    else:
        for idx, doc in enumerate(web_context_blocks, start=1):
            url = doc.get("url", "")
            content = doc.get("content", "").strip()
            lines.append(f"[{idx}] {url}")
            lines.append(content)
            lines.append("")

    lines.append("CASE_STUDY_CANDIDATES:")
    if not case_study_candidates:
        lines.append("(no case studies retrieved)")
    else:
        for chunk in case_study_candidates:
            lines.append(f"- case_id={chunk.get('case_id')} · title={chunk.get('title')}")
            lines.append(f"  excerpt: {chunk.get('content', '').strip()[:600]}")
            lines.append("")

    return "\n".join(lines)
