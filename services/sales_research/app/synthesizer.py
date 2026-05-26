"""
Claude-backed synthesizer that turns raw context into a validated SalesBrief.

Reuses services.nlp.app.llm_client for the HTTP call so we don't duplicate
Claude config, retries, or error handling.

Anti-hallucination post-processing (Task 2):
- Strict Pydantic validation against SalesBrief schema rejects malformed output.
- Citation post-filter drops any source_url not present in WEB_CONTEXT URLs.
- case_studies entries are dropped if their case_id is not in CASE_STUDY_CANDIDATES.
- After filtering, model_validator re-caps confidence to the new evidence count.
"""

from __future__ import annotations

from .contracts import SalesBrief


class SynthesizerError(Exception):
    """Raised when Claude output cannot be coerced into a valid SalesBrief."""


def synthesize_brief(
    company_name: str,
    web_context_blocks: list[dict],
    case_study_candidates: list[dict],
    icp_markdown: str | None = None,
) -> SalesBrief:
    """Run a single Claude call and return a validated SalesBrief.

    Steps:
    1. Build prompt via prompt_builder.
    2. Call Claude via services.nlp.app.llm_client.classify_complaint_with_llm-
       style helper (we will add a thin `complete_json()` wrapper).
    3. Parse JSON, strip markdown fences (reuse llm_contract helper).
    4. Validate against SalesBrief.
    5. Post-filter citations and case_studies against the allowed sources.
    6. Return the cleaned SalesBrief.
    """
    raise NotImplementedError(
        "synthesize_brief() is a Task 2 deliverable — wire Claude + Pydantic validation."
    )
