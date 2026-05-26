"""
End-to-end pipeline for generating a SalesBrief.

Orchestration order (cheap → expensive):
    cache lookup  →  web_intel (Tavily)  →  case_retriever (pgvector)
    →  synthesizer (Claude)  →  cache store

Each stage is a thin wrapper so this file stays readable and individual stages
remain unit-testable in isolation. Real implementations live in their own
module — pipeline.py only sequences them.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .cache import CACHE_TTL, lookup_cached_brief, store_brief
from .case_retriever import retrieve_case_studies
from .contracts import BriefRecord, BriefRequest, SalesBrief
from .synthesizer import synthesize_brief
from .web_intel import fetch_web_intel


class PipelineError(Exception):
    """Raised when any pipeline stage fails non-recoverably."""


def run_pipeline(request: BriefRequest, force_refresh: bool = False) -> BriefRecord:
    """Generate (or fetch from cache) a SalesBrief for the requested company.

    Returns BriefRecord including persistence metadata. The Streamlit page
    only needs `record.brief_payload` to render the one-pager.
    """
    if not force_refresh:
        cached = lookup_cached_brief(request.company_name)
        if cached is not None:
            return cached

    web = fetch_web_intel(request.company_name, industry_hint=request.industry_hint)
    case_candidates = retrieve_case_studies(
        query=request.company_name,
        industry_hint=request.industry_hint,
    )

    brief: SalesBrief = synthesize_brief(
        company_name=request.company_name,
        web_context_blocks=web.documents,
        case_study_candidates=[chunk.model_dump() for chunk in case_candidates],
    )

    now = datetime.now(UTC)
    source_urls = sorted(
        {str(c.source_url) for c in brief.snapshot_citations + brief.recent_signals}
    )
    record = BriefRecord(
        id="",  # filled by Postgres DEFAULT
        company_name=brief.company_name,
        ae_email=request.ae_email,
        generated_at=now.isoformat().replace("+00:00", "Z"),
        cached_until=(now + CACHE_TTL).isoformat().replace("+00:00", "Z"),
        confidence=brief.confidence,
        brief_payload=brief,
        source_urls=source_urls,
    )
    store_brief(record)
    return record
