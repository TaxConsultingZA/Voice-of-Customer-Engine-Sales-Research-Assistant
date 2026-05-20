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
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
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

avg_sent = round(float(df["polarity"].mean()), 3)
sentiment_label = (
    "Positive" if avg_sent >= 0.1 else "Negative" if avg_sent <= -0.1 else "Neutral"
)

high_risk_count = int(df["at_risk"].sum())
high_risk_pct = round(high_risk_count / total * 100, 1) if total else 0.0

k1, k2, k3 = st.columns(3)
with k1:
    delta_str = f"{delta_volume:+d} vs previous window" if days else "All-time view"
    st.metric("Events in view", f"{total:,}", delta=delta_str)
with k2:
    st.metric(
        "Average sentiment",
        sentiment_label,
        delta=f"Score {avg_sent:+.3f}",
        delta_color="off",
    )
with k3:
    st.metric(
        "High-risk events",
        f"{high_risk_count:,}",
        delta=f"{high_risk_pct}% of total",
        delta_color="inverse",
    )

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
        df.groupby("channel").size().reset_index(name="count")
        .sort_values("count", ascending=False)
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
        header = (
            f"{row['event_id']}  ·  {label}  ·  R{arr:,} ARR  ·  {ts}"
            f"   —   \"{preview}\""
        )
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
                f"<span class='action-chip'>{a}</span>"
                for a in humanise_actions(row["actions"])
            )
            route_chips = "".join(
                f"<span class='route-chip'>{r}</span>"
                for r in humanise_routing(row["routing"])
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

st.markdown(
    "<div class='footer'>Source: services.nlp.app.pipeline → "
    "data/processed/uec_events.jsonl · Classifier: Claude (claude-sonnet-4-6) "
    "shadow against rules baseline · Recommended actions emitted by the pipeline at classification time.</div>",
    unsafe_allow_html=True,
)
