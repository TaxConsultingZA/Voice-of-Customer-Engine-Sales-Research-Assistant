"""Voice of Customer — Weekly Intelligence Dashboard.

Run locally:
    streamlit run streamlit_app.py

Deploy to a public URL via Streamlit Community Cloud (free):
    1. Push this repo to GitHub.
    2. Go to https://share.streamlit.io and connect the repo.
    3. Pick `streamlit_app.py` as the entry point.
    4. Streamlit gives you back a shareable https URL.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

EVENT_LOG = Path("data/processed/uec_events.jsonl")
DECISION_LOG = Path("data/reports/decision_log.md")

# Friendly labels for action codes emitted by services/nlp/app/pipeline.py
ACTION_LABELS = {
    "human_review_required": "Route to human reviewer",
    "escalate_to_account_manager": "Escalate to account manager",
    "alert_security_team": "Alert security team",
    "auto_response_sent": "Auto-acknowledgement sent",
    "queue_for_processing": "Standard support queue",
    "no_action_required": "No action — informational",
}

ROUTING_LABELS = {
    "account_management": "Account Management",
    "customer_success": "Customer Success",
    "support": "Customer Support",
    "billing": "Billing Team",
    "engineering": "Engineering",
    "security": "Security",
    "product": "Product",
}

# Generic catch-all labels we don't want to surface as "top themes" — they're
# either noise (Unknown) or non-complaint traffic (positive feedback, inquiry).
GENERIC_LABELS = {
    "Support.General.Unknown",
    "Support.General.PositiveFeedback",
    "Support.General.Inquiry",
}


@st.cache_data(ttl=60)
def load_events(path: Path) -> pd.DataFrame:
    """Load UEC event log into a flat dataframe."""
    if not path.exists():
        return pd.DataFrame()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        format="ISO8601",
        utc=True,
        errors="coerce",
    )
    df["polarity"] = df["sentiment"].apply(
        lambda s: float(s.get("polarity", 0.0)) if isinstance(s, dict) else 0.0
    )
    df["at_risk"] = df["arr_linkage"].apply(
        lambda a: bool(a.get("at_risk_flag", False)) if isinstance(a, dict) else False
    )
    df["account_arr"] = df["arr_linkage"].apply(
        lambda a: float(a.get("account_arr", 0.0)) if isinstance(a, dict) else 0.0
    )
    df["text"] = df.get("raw_text_preview", "").fillna("")
    df["actions"] = df.get("actions", pd.Series([[]] * len(df))).apply(
        lambda a: a if isinstance(a, list) else []
    )
    df["routing"] = df.get("routing", pd.Series([[]] * len(df))).apply(
        lambda r: r if isinstance(r, list) else []
    )
    return df


def previous_window(df: pd.DataFrame, days: int, ref: pd.Timestamp) -> pd.DataFrame:
    """Slice the equivalent window immediately preceding the current view."""
    start = ref - pd.Timedelta(days=days * 2)
    end = ref - pd.Timedelta(days=days)
    return df[(df["timestamp"] >= start) & (df["timestamp"] < end)]


def humanise_label(path: str) -> str:
    return path.replace(".", " › ")


def humanise_actions(actions: list[str]) -> list[str]:
    return [ACTION_LABELS.get(a, a.replace("_", " ").title()) for a in actions]


def humanise_routing(routing: list[str]) -> list[str]:
    return [ROUTING_LABELS.get(r, r.replace("_", " ").title()) for r in routing]


DECISION_LOG_TEMPLATE = """\
# VoC Decision Log

This file tracks every business decision that was directly influenced by the
weekly VoC digest or dashboard.

## Decision Table

| # | Date | Decision | VoC Evidence | Owner | Outcome / Tracking |
|---|------|----------|--------------|-------|--------------------|
<!-- ROWS -->
"""


@st.cache_data(ttl=120)
def load_decision_log(path: Path) -> pd.DataFrame:
    """Parse decision_log.md table rows into a dataframe."""
    columns = ["id", "date", "decision", "evidence", "owner", "outcome"]
    if not path.exists():
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) != 6:
            continue
        if not parts[0].isdigit():
            continue
        rows.append(
            {
                "id": int(parts[0]),
                "date": parts[1],
                "decision": parts[2],
                "evidence": parts[3],
                "owner": parts[4],
                "outcome": parts[5],
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values("id", ascending=False)


def append_decision_entry(
    path: Path,
    decision: str,
    evidence: str,
    owner: str,
    outcome: str,
) -> int:
    """Append a new row to decision_log.md. Returns the new row id."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(DECISION_LOG_TEMPLATE, encoding="utf-8")

    log_text = path.read_text(encoding="utf-8")
    existing = sum(
        1
        for line in log_text.splitlines()
        if line.startswith("| ") and len(line) > 2 and line[2].isdigit()
    )
    row_id = existing + 1
    date_str = datetime.now(UTC).date().isoformat()

    new_row = f"| {row_id} | {date_str} | {decision} | {evidence} | {owner} | {outcome} |\n"
    marker = "<!-- ROWS -->"
    if marker in log_text:
        updated = log_text.replace(marker, marker + "\n" + new_row, 1)
    else:
        updated = log_text.rstrip() + "\n" + new_row
    path.write_text(updated, encoding="utf-8")
    return row_id


# ─── Page config & style ──────────────────────────────────────────────
st.set_page_config(
    page_title="Voice of Customer — Weekly Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    section.main > div { padding-top: 1.2rem; }
    .stMetric { background: rgba(255,255,255,0.02); padding: 16px 20px; border-radius: 8px;
                 border: 1px solid rgba(255,255,255,0.07); }
    .stMetric label { font-size: 0.78rem !important; color: #9da3ad !important;
                       text-transform: uppercase; letter-spacing: 0.06em; }
    .stMetric [data-testid="stMetricValue"] { font-weight: 600; font-size: 2.2rem; }
    .risk-meta { font-size: 0.82rem; color: #c9ced8; margin-bottom: 6px; }
    .risk-text { font-size: 0.95rem; color: #e9ecf2; line-height: 1.55;
                  background: rgba(255,255,255,0.03); padding: 12px 14px; border-radius: 6px;
                  border-left: 3px solid #dc2626; }
    .action-chip { display: inline-block; padding: 4px 10px; border-radius: 12px;
                    font-size: 0.78rem; margin-right: 6px; margin-top: 6px;
                    background: rgba(220,38,38,0.12); color: #fecaca;
                    border: 1px solid rgba(220,38,38,0.35); }
    .route-chip { display: inline-block; padding: 4px 10px; border-radius: 12px;
                   font-size: 0.78rem; margin-right: 6px; margin-top: 6px;
                   background: rgba(56,189,248,0.10); color: #bae6fd;
                   border: 1px solid rgba(56,189,248,0.30); }
    .footer { color: #6b7280; font-size: 0.78rem; margin-top: 32px; }
    .section-sub { color: #9da3ad; font-size: 0.85rem; margin-top: -4px; margin-bottom: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Load data ────────────────────────────────────────────────────────
df_all = load_events(EVENT_LOG)
if df_all.empty:
    st.error(
        "No event data found in data/processed/uec_events.jsonl. "
        "Run `python scripts/batch_classify_corpus.py` to populate the log."
    )
    st.stop()

# ─── Sidebar filters ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filters")

    window_options = {
        "Last 7 days": 7,
        "Last 14 days": 14,
        "Last 30 days": 30,
        "All time": None,
    }
    window_choice = st.radio(
        "Time window",
        list(window_options.keys()),
        index=0,
        label_visibility="visible",
    )
    days = window_options[window_choice]

    all_channels = sorted(df_all["channel"].dropna().unique().tolist())
    channels = st.multiselect(
        "Channels",
        all_channels,
        default=all_channels,
    )

    risk_filter = st.radio(
        "Risk level",
        ["All events", "High-risk only", "Not at-risk only"],
        index=0,
    )

    st.markdown("---")
    st.caption(
        f"Dataset: {len(df_all):,} events total · "
        f"{df_all['timestamp'].min():%Y-%m-%d} → {df_all['timestamp'].max():%Y-%m-%d}"
    )

# Apply filters
now = pd.Timestamp.now(tz="UTC")
df = df_all.copy()
if days is not None:
    df = df[df["timestamp"] >= now - pd.Timedelta(days=days)]
if channels:
    df = df[df["channel"].isin(channels)]
if risk_filter == "High-risk only":
    df = df[df["at_risk"]]
elif risk_filter == "Not at-risk only":
    df = df[~df["at_risk"]]

# ─── Header ───────────────────────────────────────────────────────────
st.markdown("### Voice of Customer — Weekly Intelligence")
filter_summary_parts = [window_choice.lower()]
if channels and len(channels) < len(all_channels):
    filter_summary_parts.append(f"{len(channels)} channel(s)")
if risk_filter != "All events":
    filter_summary_parts.append(risk_filter.lower())
st.caption(
    f"Window: {' · '.join(filter_summary_parts)} · "
    f"{len(df):,} events in view · "
    f"updated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
)
st.divider()

if df.empty:
    st.warning("No events match the current filters. Loosen the selection in the sidebar.")
    st.stop()

# ─── KPI row ──────────────────────────────────────────────────────────
total = len(df)
prev = previous_window(df_all, days or 7, now) if days else df_all.iloc[0:0]
prev_total = len(prev)
delta_volume = total - prev_total

# Sentiment polarisation — averages hide bimodal distributions, so we bucket
# every event and report the NPS-style net score plus the raw breakdown.
NEG_THRESHOLD = -0.3
POS_THRESHOLD = 0.3
angry_n = int((df["polarity"] <= NEG_THRESHOLD).sum())
positive_n = int((df["polarity"] >= POS_THRESHOLD).sum())
neutral_n = total - angry_n - positive_n
angry_pct = angry_n / total * 100 if total else 0.0
positive_pct = positive_n / total * 100 if total else 0.0
neutral_pct = neutral_n / total * 100 if total else 0.0
net_sentiment = round(positive_pct - angry_pct, 1)
if net_sentiment >= 20:
    net_label = "Healthy"
elif net_sentiment >= 0:
    net_label = "Mixed"
elif net_sentiment >= -20:
    net_label = "Strained"
else:
    net_label = "Critical"

high_risk_count = int(df["at_risk"].sum())
high_risk_pct = round(high_risk_count / total * 100, 1) if total else 0.0

k1, k2, k3 = st.columns(3)
with k1:
    delta_str = f"{delta_volume:+d} vs previous window" if days else "All-time view"
    st.metric("Events in view", f"{total:,}", delta=delta_str)
with k2:
    st.metric(
        "Net sentiment",
        f"{net_sentiment:+.1f}",
        delta=f"{net_label} · Angry {angry_pct:.0f}% / Positive {positive_pct:.0f}%",
        delta_color="inverse",
        help=(
            "Net sentiment = % positive (polarity ≥ +0.3) − % angry (polarity ≤ −0.3). "
            "Range −100 to +100. Bimodal distributions stay visible — a result that "
            "would average to ‘neutral’ will read as Strained or Critical here."
        ),
    )
with k3:
    st.metric(
        "High-risk events",
        f"{high_risk_count:,}",
        delta=f"{high_risk_pct}% of total",
        delta_color="inverse",
    )

# Sentiment distribution — stacked bar so the polarisation is impossible to miss.
sentiment_dist = pd.DataFrame(
    {
        "bucket": ["Angry (≤ −0.3)", "Neutral", "Positive (≥ +0.3)"],
        "count": [angry_n, neutral_n, positive_n],
        "pct": [angry_pct, neutral_pct, positive_pct],
    }
)
fig_dist = px.bar(
    sentiment_dist,
    x="pct",
    y=["Sentiment mix"] * 3,
    color="bucket",
    orientation="h",
    text=sentiment_dist["count"].apply(
        lambda n: f"{n:,} ({n / total * 100:.0f}%)" if total else ""
    ),
    color_discrete_map={
        "Angry (≤ −0.3)": "#dc2626",
        "Neutral": "#475569",
        "Positive (≥ +0.3)": "#16a34a",
    },
)
fig_dist.update_layout(
    barmode="stack",
    showlegend=True,
    height=110,
    margin=dict(l=8, r=8, t=8, b=8),
    xaxis=dict(range=[0, 100], showticklabels=False, title=None),
    yaxis=dict(title=None, showticklabels=False),
    legend=dict(orientation="h", yanchor="bottom", y=-0.6, xanchor="center", x=0.5),
)
fig_dist.update_traces(textposition="inside", insidetextanchor="middle")
st.plotly_chart(fig_dist, use_container_width=True)

st.divider()

# ─── Channel pie + Taxonomy bar ────────────────────────────────────────
left, right = st.columns([1, 1.1])

with left:
    st.markdown("##### Channel distribution")
    st.markdown(
        "<div class='section-sub'>Volume by intake channel.</div>",
        unsafe_allow_html=True,
    )
    channel_counts = (
        df.groupby("channel").size().reset_index(name="count").sort_values("count", ascending=False)
    )
    fig_pie = px.pie(
        channel_counts,
        names="channel",
        values="count",
        hole=0.55,
        color_discrete_sequence=px.colors.sequential.Teal_r,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(
        showlegend=True,
        margin=dict(l=8, r=8, t=8, b=8),
        height=380,
        legend=dict(orientation="v", yanchor="middle", y=0.5, x=1.0),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with right:
    st.markdown("##### Top complaint categories")
    st.markdown(
        "<div class='section-sub'>Standardised taxonomy labels — what business "
        "scenario is actually breaking.</div>",
        unsafe_allow_html=True,
    )
    label_counts = Counter(df["taxonomy_path"])
    # Drop the generic Support.General.* buckets so the chart shows real signal
    signal = [(lbl, n) for lbl, n in label_counts.items() if lbl not in GENERIC_LABELS]
    signal.sort(key=lambda x: x[1], reverse=True)
    top = signal[:10]
    if top:
        tax_df = pd.DataFrame(top, columns=["taxonomy_path", "count"])
        tax_df["label"] = tax_df["taxonomy_path"].apply(humanise_label)
        tax_df = tax_df.sort_values("count")
        fig_tax = px.bar(
            tax_df,
            x="count",
            y="label",
            orientation="h",
            color="count",
            color_continuous_scale="Reds",
            hover_data={"taxonomy_path": True, "label": False},
        )
        fig_tax.update_layout(
            coloraxis_showscale=False,
            margin=dict(l=8, r=8, t=8, b=8),
            height=380,
            yaxis_title=None,
            xaxis_title="Events",
        )
        st.plotly_chart(fig_tax, use_container_width=True)
    else:
        st.info("No specific-category complaints in the current view.")

st.divider()

# ─── Week-over-week trend ──────────────────────────────────────────────
st.markdown("##### Emerging themes — period-over-period deltas")
st.markdown(
    "<div class='section-sub'>Categories with the largest volume increase against "
    "the previous equal-length window.</div>",
    unsafe_allow_html=True,
)
if days:
    tax_cur = Counter(df["taxonomy_path"])
    tax_prev = Counter(prev["taxonomy_path"])
    deltas = []
    for path, cur in tax_cur.items():
        if path in GENERIC_LABELS:
            continue
        prev_n = tax_prev.get(path, 0)
        deltas.append((path, cur, prev_n, cur - prev_n))
    deltas.sort(key=lambda x: -x[3])
    top_deltas = [d for d in deltas if d[3] != 0][:8]
    if top_deltas:
        trend_df = pd.DataFrame(
            top_deltas, columns=["taxonomy_path", "this_window", "previous_window", "delta"]
        )
        trend_df["label"] = trend_df["taxonomy_path"].apply(humanise_label)
        trend_long = trend_df.melt(
            id_vars="label",
            value_vars=["previous_window", "this_window"],
            var_name="window",
            value_name="events",
        )
        trend_long["window"] = trend_long["window"].map(
            {"previous_window": "Previous", "this_window": "Current"}
        )
        fig_trend = px.bar(
            trend_long,
            x="label",
            y="events",
            color="window",
            barmode="group",
            color_discrete_sequence=["#475569", "#dc2626"],
        )
        fig_trend.update_layout(
            margin=dict(l=8, r=8, t=8, b=8),
            height=340,
            xaxis_title=None,
            yaxis_title="Event count",
            legend_title_text=None,
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.caption("No category movement between this window and the previous one.")
else:
    st.caption("Period-over-period comparison is disabled in All-time view.")

st.divider()

# ─── Latest high-risk alerts ───────────────────────────────────────────
st.markdown("##### Latest high-risk customer alerts")
st.markdown(
    "<div class='section-sub'>Sorted newest first. Expand any row to read the "
    "full complaint and the recommended handling.</div>",
    unsafe_allow_html=True,
)
hr = df[df["at_risk"]].copy().sort_values("timestamp", ascending=False)
hr = hr.drop_duplicates(subset=["event_id"])
hr_top = hr.head(10)

if hr_top.empty:
    st.info("No high-risk alerts in the current view.")
else:
    for _, row in hr_top.iterrows():
        ts = row["timestamp"].strftime("%Y-%m-%d %H:%M")
        arr = int(row["account_arr"]) if row["account_arr"] else 0
        label = humanise_label(row["taxonomy_path"])
        # Pull a short preview from the raw text for at-a-glance context.
        preview_raw = (row["text"] or "").strip().replace("\n", " ")
        preview = preview_raw[:60] + ("…" if len(preview_raw) > 60 else "")
        header = f"{row['event_id']}  ·  {label}  ·  R{arr:,} ARR  ·  {ts}" f'   —   "{preview}"'
        with st.expander(header, expanded=False):
            st.markdown(
                f"<div class='risk-meta'>"
                f"Channel: <b>{row['channel']}</b> · "
                f"Sentiment: <b>{row['polarity']:+.2f}</b> · "
                f"Crisis score: <b>{row['crisis_score']:.2f}</b> · "
                f"Customer hash: <code>{row['customer_id'][:16]}…</code>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='risk-text'>{row['text']}</div>",
                unsafe_allow_html=True,
            )

            action_chips = "".join(
                f"<span class='action-chip'>{a}</span>" for a in humanise_actions(row["actions"])
            )
            route_chips = "".join(
                f"<span class='route-chip'>{r}</span>" for r in humanise_routing(row["routing"])
            )
            if action_chips or route_chips:
                st.markdown("<br/>", unsafe_allow_html=True)
                st.markdown(
                    "<div class='risk-meta'><b>Recommended actions</b></div>"
                    f"<div>{action_chips or '<i>None</i>'}</div>"
                    "<div class='risk-meta' style='margin-top:10px;'><b>Route to</b></div>"
                    f"<div>{route_chips or '<i>Unassigned</i>'}</div>",
                    unsafe_allow_html=True,
                )

st.divider()

# ─── Decision traceability (no-code form + history) ────────────────────
st.markdown("##### Business decisions traced to VoC insights")
st.markdown(
    "<div class='section-sub'>Log every leadership decision driven by VoC "
    "evidence. Target: 2+ per quarter.</div>",
    unsafe_allow_html=True,
)

if "decision_panel" not in st.session_state:
    st.session_state.decision_panel = "history"

decision_df = load_decision_log(DECISION_LOG)
logged_count = len(decision_df)

# Two-button toggle row. Keep it intentionally minimal.
bcol1, bcol2, bcol3 = st.columns([1, 1, 3])
with bcol1:
    if st.button(
        "+ Add new decision",
        use_container_width=True,
        type=("primary" if st.session_state.decision_panel == "add" else "secondary"),
    ):
        st.session_state.decision_panel = "add"
with bcol2:
    if st.button(
        f"View history ({logged_count})",
        use_container_width=True,
        type=("primary" if st.session_state.decision_panel == "history" else "secondary"),
    ):
        st.session_state.decision_panel = "history"

if st.session_state.decision_panel == "add":
    with st.form("decision_form", clear_on_submit=True):
        st.markdown(
            "Fill in what was decided. The entry will be saved to "
            "`data/reports/decision_log.md`."
        )
        decision_text = st.text_input(
            "Decision taken *",
            placeholder="e.g. Redesign the checkout page",
        )
        evidence_text = st.text_input(
            "VoC evidence *",
            placeholder="e.g. Billing.Payment.DuplicateCharge +12 this week",
        )
        owner_text = st.text_input(
            "Owner (Name + Role) *",
            placeholder="e.g. Jane (Product Manager)",
        )
        outcome_text = st.text_input(
            "Outcome / how will success be tracked *",
            placeholder="e.g. Monitor weekly duplicate-charge count for 4 weeks",
        )
        submitted = st.form_submit_button("Save decision", type="primary")
        if submitted:
            fields = [
                ("Decision", decision_text),
                ("Evidence", evidence_text),
                ("Owner", owner_text),
                ("Outcome", outcome_text),
            ]
            empty = [name for name, value in fields if not value.strip()]
            blocked = [name for name, value in fields if "|" in value or "\n" in value]
            if empty:
                st.error("Please fill in: " + ", ".join(empty))
            elif blocked:
                st.error("These fields can't contain '|' or line breaks: " + ", ".join(blocked))
            else:
                new_id = append_decision_entry(
                    DECISION_LOG,
                    decision_text.strip(),
                    evidence_text.strip(),
                    owner_text.strip(),
                    outcome_text.strip(),
                )
                load_decision_log.clear()
                st.success(f"Decision #{new_id} saved.")
                st.session_state.decision_panel = "history"
                st.rerun()
else:
    if decision_df.empty:
        st.info("No decisions logged yet. Click '+ Add new decision' to record the first one.")
    else:
        st.dataframe(
            decision_df.rename(
                columns={
                    "id": "#",
                    "date": "Date",
                    "decision": "Decision",
                    "evidence": "VoC Evidence",
                    "owner": "Owner",
                    "outcome": "Outcome / Tracking",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
        if DECISION_LOG.exists():
            st.download_button(
                "Download as decision_log.md",
                data=DECISION_LOG.read_text(encoding="utf-8"),
                file_name="decision_log.md",
                mime="text/markdown",
            )

st.markdown(
    "<div class='footer'>Source: services.nlp.app.pipeline → "
    "data/processed/uec_events.jsonl · Classifier: Claude (claude-sonnet-4-6) "
    "shadow against rules baseline · Recommended actions emitted by the "
    "pipeline at classification time.</div>",
    unsafe_allow_html=True,
)
