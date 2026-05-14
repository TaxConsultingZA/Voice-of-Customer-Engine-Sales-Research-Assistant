import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path


def parse_timestamp(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)


def load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def filter_recent_events(events: list[dict], days: int, now: datetime | None = None) -> list[dict]:
    now_utc = now or datetime.now(UTC)
    cutoff = now_utc - timedelta(days=days)
    recent: list[dict] = []
    for event in events:
        ts = event.get("timestamp")
        if not ts:
            continue
        if parse_timestamp(str(ts)) >= cutoff:
            recent.append(event)
    return recent


def split_event_windows(
    events: list[dict], days: int, now: datetime | None = None
) -> tuple[list[dict], list[dict]]:
    now_utc = now or datetime.now(UTC)
    current_start = now_utc - timedelta(days=days)
    previous_start = now_utc - timedelta(days=days * 2)
    current: list[dict] = []
    previous: list[dict] = []

    for event in events:
        ts = event.get("timestamp")
        if not ts:
            continue
        event_time = parse_timestamp(str(ts))
        if event_time >= current_start:
            current.append(event)
        elif previous_start <= event_time < current_start:
            previous.append(event)
    return current, previous


def _top_anomaly_deltas(current_events: list[dict], previous_events: list[dict]) -> str:
    current_counter = Counter(
        str(e.get("taxonomy_path", "Support.General.Unknown")) for e in current_events
    )
    previous_counter = Counter(
        str(e.get("taxonomy_path", "Support.General.Unknown")) for e in previous_events
    )

    deltas: list[tuple[str, int, int, int]] = []
    for path, current_count in current_counter.items():
        previous_count = previous_counter.get(path, 0)
        delta = current_count - previous_count
        if delta > 0:
            deltas.append((path, delta, current_count, previous_count))

    deltas.sort(key=lambda item: item[1], reverse=True)
    if not deltas:
        return "- none"
    lines = [
        f"- {path}: +{delta} (current={current_count}, previous={previous_count})"
        for path, delta, current_count, previous_count in deltas[:5]
    ]
    return "\n".join(lines)


def _high_arr_risk_accounts(events: list[dict], min_arr: float = 100000.0) -> str:
    account_stats: dict[str, dict] = {}
    for event in events:
        customer_id = str(event.get("customer_id", ""))
        if not customer_id:
            continue
        arr_linkage = event.get("arr_linkage")
        if not isinstance(arr_linkage, dict):
            continue
        account_arr = float(arr_linkage.get("account_arr", 0.0))
        at_risk = bool(arr_linkage.get("at_risk_flag", False))
        if account_arr < min_arr or not at_risk:
            continue

        stats = account_stats.setdefault(
            customer_id,
            {"max_arr": 0.0, "at_risk_events": 0, "negative_events": 0},
        )
        stats["max_arr"] = max(stats["max_arr"], account_arr)
        stats["at_risk_events"] += 1
        sentiment = event.get("sentiment")
        if isinstance(sentiment, dict) and float(sentiment.get("polarity", 0.0)) < -0.1:
            stats["negative_events"] += 1

    if not account_stats:
        return "- none"

    ranked = sorted(
        account_stats.items(),
        key=lambda item: (item[1]["max_arr"], item[1]["at_risk_events"]),
        reverse=True,
    )
    lines = [
        f"- customer_hash={customer_id[:12]}..., arr={int(stats['max_arr'])}, "
        f"at_risk_events={stats['at_risk_events']}, negative_events={stats['negative_events']}"
        for customer_id, stats in ranked[:10]
    ]
    return "\n".join(lines)


def build_weekly_digest(
    events: list[dict],
    generated_at: datetime | None = None,
    previous_events: list[dict] | None = None,
) -> str:
    generated = generated_at or datetime.now(UTC)
    total = len(events)
    unique_customers = len({e.get("customer_id", "") for e in events if e.get("customer_id")})
    channel_counter = Counter(str(e.get("channel", "unknown")) for e in events)
    taxonomy_counter = Counter(
        str(e.get("taxonomy_path", "Support.General.Unknown")) for e in events
    )
    intent_counter = Counter(str(e.get("intent", "unknown")) for e in events)
    at_risk = sum(
        1
        for e in events
        if isinstance(e.get("arr_linkage"), dict) and bool(e["arr_linkage"].get("at_risk_flag"))
    )
    negative = sum(
        1
        for e in events
        if isinstance(e.get("sentiment"), dict)
        and float(e["sentiment"].get("polarity", 0.0)) < -0.1
    )

    top_channels = (
        "\n".join(f"- {channel}: {count}" for channel, count in channel_counter.most_common(5))
        or "- none"
    )
    top_taxonomies = (
        "\n".join(f"- {path}: {count}" for path, count in taxonomy_counter.most_common(5))
        or "- none"
    )
    top_intents = (
        "\n".join(f"- {intent}: {count}" for intent, count in intent_counter.most_common(5))
        or "- none"
    )
    anomaly_deltas = _top_anomaly_deltas(events, previous_events or [])
    high_arr_accounts = _high_arr_risk_accounts(events)

    return (
        "# Weekly VoC Digest\n\n"
        f"Generated at (UTC): {generated.isoformat().replace('+00:00', 'Z')}\n\n"
        "## Volume Summary\n"
        f"- Total events: {total}\n"
        f"- Unique customers: {unique_customers}\n"
        f"- At-risk flagged events: {at_risk}\n"
        f"- Negative sentiment events: {negative}\n\n"
        "## Top Channels\n"
        f"{top_channels}\n\n"
        "## Top Taxonomy Themes\n"
        f"{top_taxonomies}\n\n"
        "## Top Intents\n"
        f"{top_intents}\n\n"
        "## Emerging Theme Deltas (vs previous window)\n"
        f"{anomaly_deltas}\n\n"
        "## High ARR At-Risk Accounts\n"
        f"{high_arr_accounts}\n"
    )
