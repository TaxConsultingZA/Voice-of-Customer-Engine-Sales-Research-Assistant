"""
Sales Research Assistant — Streamlit page.

Sits alongside streamlit_app.py via Streamlit's native multi-page convention:
    streamlit_app.py            -> "Home" (VoC Dashboard)
    pages/01_Sales_Research.py  -> "Sales Research" (this page)

While the pipeline backend is being implemented (Tasks 1-3), this page renders
a single read-only example brief so the team can review layout and copy
without depending on Claude/Tavily being wired up.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import streamlit as st

st.set_page_config(
    page_title="Sales Research - Pre-call Brief",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_brief(brief: dict, force_refresh: bool, ae_email: str) -> None:
    confidence = brief.get("confidence", 0.0)
    confidence_pct = int(round(confidence * 100))

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.markdown(f"## {brief['company_name']}")
        if brief.get("snapshot"):
            st.markdown(brief["snapshot"])
        for citation in brief.get("snapshot_citations", []):
            st.caption(
                f"-> {citation['text']} - " f"[{citation['source_url']}]({citation['source_url']})"
            )
    with top_right:
        bar = "Healthy" if confidence >= 0.7 else ("Mixed" if confidence >= 0.4 else "Thin")
        st.metric("Confidence", f"{confidence_pct}%", delta=bar)
        st.caption(
            "Skeleton: live pipeline pending."
            if force_refresh
            else f"AE: {ae_email or 'anonymous'}"
        )

    st.divider()

    st.markdown("#### Recent signals")
    signals = brief.get("recent_signals", []) or []
    if not signals:
        st.caption("No recent signals found.")
    for sig in signals:
        st.markdown(f"- {sig['text']} - [{sig['source_url']}]({sig['source_url']})")

    st.markdown("#### Likely pain points")
    pains = brief.get("pain_points", []) or []
    if not pains:
        st.caption("No pain points inferred.")
    for pain in pains:
        with st.expander(f"{pain['title']}  ·  severity: {pain['severity']}", expanded=False):
            st.write(pain["description"])
            for citation in pain.get("citations", []):
                st.caption(
                    f"-> {citation['text']} - "
                    f"[{citation['source_url']}]({citation['source_url']})"
                )

    st.markdown("#### Relevant case studies")
    cases = brief.get("case_studies", []) or []
    if not cases:
        st.caption("No case studies matched.")
    for case in cases:
        st.markdown(
            f"- **{case['title']}**  ·  case_id `{case['case_id']}`  ·  "
            f"relevance {case['relevance_score']:.2f}"
        )
        st.caption(case["why_relevant"])

    st.markdown("#### Discovery questions")
    qs = brief.get("discovery_questions", []) or []
    if not qs:
        st.caption("No discovery questions generated.")
    for q in qs:
        st.markdown(f"- _{q['question']}_")
        st.caption(f"{q['rationale']}  ·  linked: {q.get('linked_pain_point') or 'none'}")

    st.divider()
    st.download_button(
        "Download brief (.json)",
        data=json.dumps(brief, indent=2, ensure_ascii=False),
        file_name=f"sales_brief_{brief['company_name']}_{datetime.now(UTC).date()}.json",
        mime="application/json",
    )

    st.caption(
        "Skeleton view. Real pipeline will replace this static brief with "
        "services.sales_research.app.pipeline.run_pipeline output."
    )


st.markdown("### Sales Research - Pre-call Brief")
st.caption(
    "Generate a one-page brief from public web + internal case studies. "
    "Skeleton page - pipeline backend is in development."
)
st.divider()

with st.form("brief_form"):
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company_name = st.text_input("Target company *", placeholder="e.g. ACME Bank")
    with col_b:
        industry_hint = st.text_input("Industry hint (optional)", placeholder="e.g. banking")

    col_c, col_d = st.columns([2, 1])
    with col_c:
        ae_email = st.text_input(
            "Your work email (for feedback tracking)",
            placeholder="jane@taxconsulting.co.za",
        )
    with col_d:
        force_refresh = st.checkbox(
            "Force refresh (skip 7-day cache)",
            value=False,
            help="Bypass cache and regenerate. Costs Tavily + Claude calls.",
        )

    submitted = st.form_submit_button("Generate brief", type="primary")

if submitted:
    if not company_name.strip():
        st.error("Please enter a target company.")
        st.stop()

    st.info(
        "Backend not wired yet. Showing a static example so layout can be reviewed. "
        "Replace this branch with a call to services.sales_research.app.pipeline."
    )

    example_brief = {
        "company_name": company_name,
        "snapshot": (
            "Example FinTech subsidiary, ~1,200 staff, Cape Town HQ. "
            "Replace with real pipeline output once Tasks 1-3 are complete."
        ),
        "snapshot_citations": [
            {
                "text": "ACME Group HQ in Cape Town",
                "source_url": "https://example.com/about",
            }
        ],
        "recent_signals": [
            {
                "text": "Announced FedNow integration in May 2026",
                "source_url": "https://example.com/news/fednow",
            }
        ],
        "pain_points": [
            {
                "title": "ComplianceReportingBurden",
                "description": "New SARB rules tightening compliance windows.",
                "severity": "high",
                "citations": [
                    {
                        "text": "CEO interview citing compliance pressure",
                        "source_url": "https://example.com/news/ceo",
                    }
                ],
            }
        ],
        "case_studies": [
            {
                "case_id": "case_fnb_compliance_001",
                "title": "FNB: compliance reporting cut from 9 days to 4 hours",
                "relevance_score": 0.82,
                "why_relevant": "Same SARB regime, similar scale.",
            }
        ],
        "discovery_questions": [
            {
                "question": "How is your team handling the new SARB compliance window?",
                "rationale": "Anchored in the CEO interview signal.",
                "linked_pain_point": "ComplianceReportingBurden",
            }
        ],
        "confidence": 0.35,
    }
    _render_brief(example_brief, force_refresh=force_refresh, ae_email=ae_email)
else:
    st.caption("Fill the form above and click Generate brief.")
