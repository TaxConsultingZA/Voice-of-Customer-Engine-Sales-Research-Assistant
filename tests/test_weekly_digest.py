from datetime import UTC, datetime

from services.ingestion.app.digest import (
    build_weekly_digest,
    filter_recent_events,
    split_event_windows,
)


def _event(
    *,
    timestamp: str,
    channel: str,
    taxonomy_path: str,
    customer_id: str,
    polarity: float,
    intent: str,
    at_risk: bool,
) -> dict:
    return {
        "event_id": f"id-{customer_id}-{channel}",
        "timestamp": timestamp,
        "channel": channel,
        "customer_id": customer_id,
        "sentiment": {"polarity": polarity, "confidence": 0.8},
        "taxonomy_path": taxonomy_path,
        "intent": intent,
        "arr_linkage": {"account_arr": 10000, "at_risk_flag": at_risk},
    }


def test_filter_recent_events_applies_window():
    now = datetime(2026, 5, 14, tzinfo=UTC)
    events = [
        _event(
            timestamp="2026-05-13T12:00:00Z",
            channel="email",
            taxonomy_path="Authentication.Login.Failure",
            customer_id="a",
            polarity=-0.6,
            intent="complaint",
            at_risk=True,
        ),
        _event(
            timestamp="2026-04-01T12:00:00Z",
            channel="whatsapp",
            taxonomy_path="Billing.Payment.Failure",
            customer_id="b",
            polarity=-0.2,
            intent="complaint",
            at_risk=False,
        ),
    ]
    recent = filter_recent_events(events, days=7, now=now)
    assert len(recent) == 1
    assert recent[0]["customer_id"] == "a"


def test_build_weekly_digest_contains_key_sections():
    events = [
        _event(
            timestamp="2026-05-13T12:00:00Z",
            channel="email",
            taxonomy_path="Authentication.Login.Failure",
            customer_id="a",
            polarity=-0.6,
            intent="complaint",
            at_risk=True,
        ),
        _event(
            timestamp="2026-05-13T13:00:00Z",
            channel="email",
            taxonomy_path="Authentication.Login.Failure",
            customer_id="c",
            polarity=-0.4,
            intent="complaint",
            at_risk=False,
        ),
        _event(
            timestamp="2026-05-13T14:00:00Z",
            channel="whatsapp",
            taxonomy_path="Billing.Payment.Failure",
            customer_id="b",
            polarity=0.1,
            intent="question",
            at_risk=False,
        ),
    ]

    digest = build_weekly_digest(events, generated_at=datetime(2026, 5, 14, tzinfo=UTC))
    assert "Weekly VoC Digest" in digest
    assert "Total events: 3" in digest
    assert "Unique customers: 3" in digest
    assert "At-risk flagged events: 1" in digest
    assert "Negative sentiment events: 2" in digest
    assert "Authentication.Login.Failure: 2" in digest
    assert "- email: 2" in digest
    assert "Emerging Theme Deltas (vs previous window)" in digest
    assert "High ARR At-Risk Accounts" in digest


def test_split_event_windows_separates_current_and_previous():
    now = datetime(2026, 5, 14, tzinfo=UTC)
    events = [
        _event(
            timestamp="2026-05-13T12:00:00Z",
            channel="email",
            taxonomy_path="Authentication.Login.Failure",
            customer_id="a",
            polarity=-0.6,
            intent="complaint",
            at_risk=True,
        ),
        _event(
            timestamp="2026-05-06T12:00:00Z",
            channel="email",
            taxonomy_path="Billing.Payment.Failure",
            customer_id="b",
            polarity=-0.3,
            intent="complaint",
            at_risk=True,
        ),
    ]
    current, previous = split_event_windows(events, days=7, now=now)
    assert len(current) == 1
    assert len(previous) == 1


def test_digest_shows_theme_delta_and_high_arr_accounts():
    current_events = [
        _event(
            timestamp="2026-05-13T12:00:00Z",
            channel="email",
            taxonomy_path="Authentication.Login.Failure",
            customer_id="high-arr-customer",
            polarity=-0.8,
            intent="complaint",
            at_risk=True,
        ),
        _event(
            timestamp="2026-05-13T13:00:00Z",
            channel="email",
            taxonomy_path="Authentication.Login.Failure",
            customer_id="high-arr-customer",
            polarity=-0.6,
            intent="complaint",
            at_risk=True,
        ),
    ]
    current_events[0]["arr_linkage"]["account_arr"] = 250000
    current_events[1]["arr_linkage"]["account_arr"] = 250000

    previous_events = [
        _event(
            timestamp="2026-05-05T12:00:00Z",
            channel="email",
            taxonomy_path="Authentication.Login.Failure",
            customer_id="high-arr-customer",
            polarity=-0.2,
            intent="complaint",
            at_risk=False,
        )
    ]
    previous_events[0]["arr_linkage"]["account_arr"] = 250000

    digest = build_weekly_digest(
        current_events,
        generated_at=datetime(2026, 5, 14, tzinfo=UTC),
        previous_events=previous_events,
    )
    assert "Authentication.Login.Failure: +1 (current=2, previous=1)" in digest
    assert "customer_hash=high-arr-cus" in digest
