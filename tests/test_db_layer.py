"""
Tests for the PostgreSQL persistence layer.

All tests run without a live database. They verify that every DB helper
degrades gracefully to a no-op when DATABASE_URL is not set, so the service
continues to work in local dev and CI without a Postgres instance.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


# ── db.get_db ─────────────────────────────────────────────────────────────────


def test_ingestion_get_db_yields_none_when_no_url():
    from services.ingestion.app.db import get_db

    with get_db() as conn:
        assert conn is None


def test_decision_get_db_yields_none_when_no_url():
    from services.decision.app.db import get_db

    with get_db() as conn:
        assert conn is None


# ── event_store._persist_to_db ────────────────────────────────────────────────


def test_persist_to_db_is_noop_without_url(tmp_path, monkeypatch):
    monkeypatch.setenv("INGESTION_EVENT_LOG_PATH", str(tmp_path / "events.jsonl"))
    from services.ingestion.app.event_store import _persist_to_db

    _persist_to_db({"event_id": "test-1", "channel": "email"})


# ── engine helpers ────────────────────────────────────────────────────────────


def test_restore_state_from_db_is_noop_without_url():
    from services.decision.app.engine import clear_state, restore_state_from_db

    clear_state()
    restore_state_from_db()
    from services.decision.app.engine import _pending_store

    assert len(_pending_store) == 0


def test_db_persist_decision_is_noop_without_url():
    from services.decision.app.engine import _db_persist_decision
    from services.decision.app.models import Decision, DecisionStatus

    d = Decision(
        decision_id="noop-1",
        status=DecisionStatus.AUTO_RESOLVED,
        approved_actions=[],
        blocked_actions=[],
        escalation_tier="green",
        watchlist_flag=False,
        customer_arr=0.0,
        crisis_score=0.1,
        created_at="2026-01-01T00:00:00Z",
    )
    _db_persist_decision(d)


def test_db_update_decision_is_noop_without_url():
    from services.decision.app.engine import _db_update_decision
    from services.decision.app.models import Decision, DecisionStatus

    d = Decision(
        decision_id="noop-2",
        status=DecisionStatus.APPROVED,
        approved_actions=["send_email"],
        blocked_actions=[],
        escalation_tier="red",
        watchlist_flag=False,
        customer_arr=50000.0,
        crisis_score=0.7,
        created_at="2026-01-01T00:00:00Z",
        resolved_at="2026-01-01T01:00:00Z",
        resolved_by="agent",
    )
    _db_update_decision(d)


# ── watchlist DB helpers ───────────────────────────────────────────────────────


def test_watchlist_db_upsert_is_noop_without_url():
    from services.decision.app.watchlist import Watchlist

    w = Watchlist()
    w.add("cust-999", 120_000.0)
    assert w.is_on_watchlist("cust-999")


def test_watchlist_db_delete_is_noop_without_url():
    from services.decision.app.watchlist import Watchlist

    w = Watchlist()
    w._entries["cust-999"] = 120_000.0
    removed = w.remove("cust-999")
    assert removed
    assert not w.is_on_watchlist("cust-999")
