"""
Decision Engine Tests
----------------------
Validates the governance gate logic, approval workflow, watchlist behaviour,
and escalation routing. All tests run without external services.
"""

import pytest

from services.decision.app.engine import (
    RED_THRESHOLD,
    YELLOW_THRESHOLD,
    approve_decision,
    clear_state,
    decide,
    get_watchlist,
    list_pending,
    reject_decision,
)
from services.decision.app.models import DecisionRequest, DecisionStatus
from services.decision.app.watchlist import HIGH_ARR_THRESHOLD


@pytest.fixture(autouse=True)
def reset_engine():
    """Isolate every test — clear in-memory pending store and watchlist."""
    clear_state()
    yield
    clear_state()


def _req(
    crisis_score: float,
    arr: float = 0.0,
    customer_id: str = "",
    intent: str = "complaint",
    actions: list[str] | None = None,
) -> DecisionRequest:
    return DecisionRequest(
        text="test complaint",
        crisis_score=crisis_score,
        intent=intent,
        customer_arr=arr,
        customer_id=customer_id,
        actions=actions or ["notify_customer_success"],
    )


# ---------------------------------------------------------------------------
# Gate boundaries
# ---------------------------------------------------------------------------


def test_green_score_is_auto_resolved():
    decision = decide(_req(crisis_score=0.1))
    assert decision.status == DecisionStatus.AUTO_RESOLVED
    assert decision.escalation_tier == "green"
    assert len(decision.approved_actions) > 0
    assert decision.blocked_actions == []


def test_yellow_score_is_auto_notify():
    decision = decide(_req(crisis_score=0.45))
    assert decision.status == DecisionStatus.AUTO_NOTIFY
    assert decision.escalation_tier == "yellow"
    assert len(decision.approved_actions) > 0
    assert decision.blocked_actions == []


def test_red_score_is_pending_approval():
    decision = decide(_req(crisis_score=0.75))
    assert decision.status == DecisionStatus.PENDING_APPROVAL
    assert decision.escalation_tier == "red"
    assert decision.approved_actions == []
    assert len(decision.blocked_actions) > 0


def test_red_threshold_boundary():
    at_red = decide(_req(crisis_score=RED_THRESHOLD))
    assert at_red.status == DecisionStatus.PENDING_APPROVAL

    just_below = decide(_req(crisis_score=RED_THRESHOLD - 0.001))
    assert just_below.status in (DecisionStatus.AUTO_NOTIFY, DecisionStatus.PENDING_APPROVAL)


def test_yellow_threshold_boundary():
    at_yellow = decide(_req(crisis_score=YELLOW_THRESHOLD))
    assert at_yellow.status == DecisionStatus.AUTO_NOTIFY

    just_below = decide(_req(crisis_score=YELLOW_THRESHOLD - 0.001))
    assert just_below.status == DecisionStatus.AUTO_RESOLVED


# ---------------------------------------------------------------------------
# Watchlist — high-ARR override
# ---------------------------------------------------------------------------


def test_high_arr_yellow_score_is_pending():
    decision = decide(_req(crisis_score=0.45, arr=HIGH_ARR_THRESHOLD, customer_id="cust_001"))
    assert decision.status == DecisionStatus.PENDING_APPROVAL
    assert decision.escalation_tier == "watchlist"
    assert decision.watchlist_flag is True


def test_high_arr_auto_enrolls_customer():
    decide(_req(crisis_score=0.45, arr=HIGH_ARR_THRESHOLD, customer_id="cust_002"))
    assert get_watchlist().is_on_watchlist("cust_002")


def test_watchlisted_customer_always_pending():
    get_watchlist().add("vip_customer", 50_000)
    decision = decide(_req(crisis_score=0.1, arr=50_000, customer_id="vip_customer"))
    assert decision.status == DecisionStatus.PENDING_APPROVAL
    assert decision.watchlist_flag is True


def test_low_arr_is_not_watchlisted():
    decision = decide(_req(crisis_score=0.2, arr=10_000, customer_id="smb_001"))
    assert decision.watchlist_flag is False
    assert not get_watchlist().is_on_watchlist("smb_001")


def test_arr_just_below_threshold_is_not_watchlisted():
    decision = decide(_req(crisis_score=0.45, arr=HIGH_ARR_THRESHOLD - 1, customer_id="near_001"))
    assert decision.escalation_tier == "yellow"
    assert decision.watchlist_flag is False


# ---------------------------------------------------------------------------
# Pending store
# ---------------------------------------------------------------------------


def test_red_decision_lands_in_pending_store():
    decision = decide(_req(crisis_score=0.8))
    pending = list_pending()
    ids = [d.decision_id for d in pending]
    assert decision.decision_id in ids


def test_green_decision_not_in_pending_store():
    decide(_req(crisis_score=0.1))
    assert list_pending() == []


def test_multiple_red_decisions_all_in_pending():
    d1 = decide(_req(crisis_score=0.7))
    d2 = decide(_req(crisis_score=0.8))
    ids = {d.decision_id for d in list_pending()}
    assert d1.decision_id in ids
    assert d2.decision_id in ids


# ---------------------------------------------------------------------------
# Approve workflow
# ---------------------------------------------------------------------------


def test_approve_releases_blocked_actions():
    decision = decide(_req(crisis_score=0.75, actions=["escalate_to_account_manager"]))
    approved = approve_decision(decision.decision_id, approved_by="cse_team")

    assert approved is not None
    assert approved.status == DecisionStatus.APPROVED
    assert "escalate_to_account_manager" in approved.approved_actions
    assert approved.blocked_actions == []
    assert approved.resolved_by == "cse_team"
    assert approved.resolved_at is not None


def test_approve_removes_from_pending():
    decision = decide(_req(crisis_score=0.8))
    approve_decision(decision.decision_id)
    pending_ids = [d.decision_id for d in list_pending()]
    assert decision.decision_id not in pending_ids


def test_approve_unknown_id_returns_none():
    result = approve_decision("non-existent-id")
    assert result is None


# ---------------------------------------------------------------------------
# Reject workflow
# ---------------------------------------------------------------------------


def test_reject_keeps_blocked_actions_empty():
    decision = decide(_req(crisis_score=0.75))
    rejected = reject_decision(
        decision.decision_id, rejected_by="compliance_team", notes="Risk too high"
    )

    assert rejected is not None
    assert rejected.status == DecisionStatus.REJECTED
    assert rejected.approved_actions == []
    assert rejected.resolved_by == "compliance_team"
    assert rejected.notes == "Risk too high"


def test_reject_removes_from_pending():
    decision = decide(_req(crisis_score=0.8))
    reject_decision(decision.decision_id)
    pending_ids = [d.decision_id for d in list_pending()]
    assert decision.decision_id not in pending_ids


def test_reject_unknown_id_returns_none():
    result = reject_decision("ghost-id")
    assert result is None


# ---------------------------------------------------------------------------
# Decision metadata
# ---------------------------------------------------------------------------


def test_decision_id_is_unique():
    d1 = decide(_req(crisis_score=0.8))
    d2 = decide(_req(crisis_score=0.8))
    assert d1.decision_id != d2.decision_id


def test_decision_stores_crisis_score():
    decision = decide(_req(crisis_score=0.72))
    assert decision.crisis_score == 0.72


def test_decision_stores_arr():
    decision = decide(_req(crisis_score=0.5, arr=75_000))
    assert decision.customer_arr == 75_000


def test_created_at_is_iso8601():
    import re

    decision = decide(_req(crisis_score=0.4))
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", decision.created_at)


# ---------------------------------------------------------------------------
# Watchlist CRUD
# ---------------------------------------------------------------------------


def test_watchlist_add_and_query():
    wl = get_watchlist()
    wl.add("enterprise_001", 250_000)
    assert wl.is_on_watchlist("enterprise_001")


def test_watchlist_remove():
    wl = get_watchlist()
    wl.add("to_remove", 150_000)
    removed = wl.remove("to_remove")
    assert removed is True
    assert not wl.is_on_watchlist("to_remove")


def test_watchlist_remove_missing_returns_false():
    wl = get_watchlist()
    assert wl.remove("does_not_exist") is False


def test_watchlist_list_entries():
    wl = get_watchlist()
    wl.add("cust_a", 120_000)
    wl.add("cust_b", 200_000)
    entries = wl.list_entries()
    assert "cust_a" in entries
    assert "cust_b" in entries


def test_is_high_arr_threshold():
    wl = get_watchlist()
    assert wl.is_high_arr(HIGH_ARR_THRESHOLD) is True
    assert wl.is_high_arr(HIGH_ARR_THRESHOLD - 1) is False
