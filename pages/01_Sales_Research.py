"""
Sales Research Assistant — Streamlit page.

Sits alongside streamlit_app.py via Streamlit's native multi-page convention:
    streamlit_app.py            -> "Home" (VoC Dashboard)
    pages/01_Sales_Research.py  -> "Sales Research" (this page)
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

# Ensure the project root is on sys.path so `services.*` imports resolve
# regardless of which directory Streamlit was launched from.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.sales_research.app.contracts import BriefRequest  # noqa: E402
from services.sales_research.app.pipeline import PipelineError, run_pipeline  # noqa: E402
from services.sales_research.app.synthesizer import SynthesizerError  # noqa: E402

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
            f"AE: {ae_email or 'anonymous'}" + (" · force-refreshed" if force_refresh else "")
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


st.markdown("### Sales Research - Pre-call Brief")
st.caption(
    "Generate a one-page brief from public web + internal case studies. "
    "Requires CLAUDE_API_KEY and TAVILY_API_KEY in .env."
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

    with st.spinner(f"Researching {company_name.strip()}… (may take up to 30s)"):
        try:
            req = BriefRequest(
                company_name=company_name.strip(),
                ae_email=ae_email.strip() or None,
                industry_hint=industry_hint.strip() or None,
            )
            record = run_pipeline(req, force_refresh=force_refresh)
            _render_brief(record.brief_payload.model_dump(), force_refresh, ae_email)
        except SynthesizerError as exc:
            st.error(f"Claude synthesis failed: {exc}")
        except PipelineError as exc:
            st.error(f"Pipeline error: {exc}")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
else:
    st.caption("Fill the form above and click Generate brief.")
