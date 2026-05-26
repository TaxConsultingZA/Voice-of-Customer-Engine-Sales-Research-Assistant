"""
Pydantic contracts for the Sales Research Assistant pipeline.

These models are the single source of truth for:
- Claude's JSON output shape (strict validation)
- PostgreSQL `sales_briefs.brief_payload` JSONB column
- Streamlit page rendering
- pgvector case study retrieval results

Anti-hallucination guarantees enforced at model level:
- Every Citation MUST have a non-empty source_url
- snapshot_citations and recent_signals require >= 1 citation each
- pain_points must reference at least one citation OR the ICP
- case_studies must reference a case_id present in the case library
- confidence is clamped to <= 0.4 when fewer than 2 distinct sources exist
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class Citation(BaseModel):
    """A single fact statement with its mandatory source URL."""

    text: str = Field(..., min_length=3, max_length=400)
    source_url: str = Field(..., description="Public URL backing this claim.")

    @field_validator("source_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        if not _URL_RE.match(value):
            raise ValueError("source_url must start with http:// or https://")
        return value


class PainPoint(BaseModel):
    """A pain point inferred from web signals matched against our ICP."""

    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10, max_length=600)
    severity: Literal["high", "medium", "low"]
    citations: list[Citation] = Field(..., min_length=1, max_length=4)


class CaseStudyMatch(BaseModel):
    """A reference to an internal case study suggested for the call."""

    case_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=3, max_length=200)
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    why_relevant: str = Field(..., min_length=10, max_length=400)


class DiscoveryQuestion(BaseModel):
    """A discovery question crafted for the AE to open the call with."""

    question: str = Field(..., min_length=10, max_length=300)
    rationale: str = Field(..., min_length=5, max_length=240)
    linked_pain_point: str | None = Field(
        default=None,
        description="Title of the pain point this question explores; null if generic.",
    )


class SalesBrief(BaseModel):
    """The full one-page brief returned to the AE."""

    company_name: str = Field(..., min_length=1, max_length=200)
    snapshot: str = Field(default="", max_length=1200)
    snapshot_citations: list[Citation] = Field(default_factory=list, max_length=6)
    recent_signals: list[Citation] = Field(default_factory=list, max_length=8)
    pain_points: list[PainPoint] = Field(default_factory=list, max_length=3)
    case_studies: list[CaseStudyMatch] = Field(default_factory=list, max_length=3)
    discovery_questions: list[DiscoveryQuestion] = Field(default_factory=list, max_length=5)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _enforce_low_confidence_on_thin_evidence(self) -> "SalesBrief":
        """If fewer than 2 distinct credible URLs back the brief, cap confidence."""
        distinct_urls: set[str] = set()
        for citation in self.snapshot_citations + self.recent_signals:
            distinct_urls.add(str(citation.source_url))
        for pain in self.pain_points:
            for citation in pain.citations:
                distinct_urls.add(str(citation.source_url))

        if len(distinct_urls) < 2 and self.confidence > 0.4:
            # Hard cap — protects AE from over-confident output on thin data.
            object.__setattr__(self, "confidence", 0.4)
        return self


class CaseStudyChunk(BaseModel):
    """A vector store row used by case_retriever.py."""

    case_id: str
    title: str
    chunk_index: int
    content: str
    industry_tags: list[str] = Field(default_factory=list)


class WebIntelResult(BaseModel):
    """Output of the Tavily-backed web intel pass."""

    query: str
    fetched_at: str
    documents: list[dict] = Field(default_factory=list)


class BriefRequest(BaseModel):
    """Request payload posted from the Streamlit page to the pipeline."""

    company_name: str = Field(..., min_length=1, max_length=200)
    ae_email: str | None = Field(default=None, max_length=200)
    industry_hint: str | None = Field(default=None, max_length=120)


class BriefRecord(BaseModel):
    """Persisted record stored in sales_briefs Postgres table."""

    id: str
    company_name: str
    ae_email: str | None
    generated_at: str
    cached_until: str
    confidence: float
    brief_payload: SalesBrief
    source_urls: list[HttpUrl]
