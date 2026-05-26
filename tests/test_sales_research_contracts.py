"""Tests for the Sales Research Pydantic contracts.

We test contracts.py because it is the single point of truth that every other
module in services/sales_research/ depends on. Stubs in web_intel /
case_retriever / synthesizer / cache deliberately raise NotImplementedError
and are excluded from coverage until they ship.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.sales_research.app.contracts import (
    BriefRequest,
    Citation,
    DiscoveryQuestion,
    PainPoint,
    SalesBrief,
)


def _make_citation(url: str = "https://news.example.com/a") -> Citation:
    return Citation(text="ACME reported R2.4B revenue", source_url=url)


def test_citation_requires_http_scheme():
    with pytest.raises(ValidationError):
        Citation(text="bad", source_url="ftp://example.com/a")


def test_pain_point_requires_at_least_one_citation():
    with pytest.raises(ValidationError):
        PainPoint(
            title="ComplianceReportingBurden",
            description="A description longer than ten chars.",
            severity="high",
            citations=[],
        )


def test_discovery_question_allows_null_linked_pain_point():
    q = DiscoveryQuestion(
        question="How are you handling the new SARB compliance window today?",
        rationale="Anchored in CEO interview.",
        linked_pain_point=None,
    )
    assert q.linked_pain_point is None


def test_sales_brief_low_confidence_capped_when_thin_evidence():
    brief = SalesBrief(
        company_name="ACME Bank",
        snapshot="Snapshot text",
        snapshot_citations=[_make_citation()],
        recent_signals=[],
        pain_points=[],
        case_studies=[],
        discovery_questions=[],
        confidence=0.9,
    )
    # Only one distinct URL across all citations -> hard cap at 0.4.
    assert brief.confidence == 0.4


def test_sales_brief_keeps_high_confidence_when_evidence_is_diverse():
    cites = [
        _make_citation("https://a.example.com"),
        _make_citation("https://b.example.com"),
        _make_citation("https://c.example.com"),
        _make_citation("https://d.example.com"),
    ]
    brief = SalesBrief(
        company_name="ACME Bank",
        snapshot="Diverse evidence snapshot.",
        snapshot_citations=cites[:2],
        recent_signals=cites[2:],
        pain_points=[],
        case_studies=[],
        discovery_questions=[],
        confidence=0.85,
    )
    assert brief.confidence == 0.85


def test_sales_brief_caps_pain_points_to_three():
    cites = [_make_citation()]
    pains = [
        PainPoint(
            title=f"Pain {i}",
            description="A description longer than ten chars.",
            severity="medium",
            citations=cites,
        )
        for i in range(5)
    ]
    with pytest.raises(ValidationError):
        SalesBrief(
            company_name="ACME",
            snapshot="x",
            snapshot_citations=cites,
            recent_signals=cites,
            pain_points=pains,
            case_studies=[],
            discovery_questions=[],
            confidence=0.5,
        )


def test_brief_request_min_company_name():
    with pytest.raises(ValidationError):
        BriefRequest(company_name="")
