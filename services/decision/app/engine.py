"""
Decision Intelligence Engine — core decision logic.

Governance gates:
    Green   crisis_score < 0.3                → AUTO_RESOLVED
    Yellow  0.3 ≤ crisis_score < 0.6          → AUTO_NOTIFY
    Red     crisis_score ≥ 0.6                → PENDING_APPROVAL (blocked)
    Watchlist  customer on watchlist OR ARR ≥ R100K  → PENDING_APPROVAL (blocked)

Watchlist customers are auto-enrolled on their first high-ARR signal.
"""

import uuid
from datetime import datetime, timezone

from .models import Decision, DecisionRequest, DecisionStatus
from .watchlist import HIGH_ARR_THRESHOLD, Watchlist

RED_THRESHOLD = 0.6
YELLOW_THRESHOLD = 0.3

_watchlist = Watchlist()
_pending_store: dict[str, Decision] = {}


def _get_escalation_tier(crisis_score: float, on_watchlist: bool, arr: float) -> str:
    if crisis_score >= RED_THRESHOLD:
        return "red"
    if on_watchlist or arr >= HIGH_ARR_THRESHOLD:
        return "watchlist"
    if crisis_score >= YELLOW_THRESHOLD:
        return "yellow"
    return "green"


def decide(req: DecisionRequest) -> Decision:
    on_watchlist = _watchlist.is_on_watchlist(req.customer_id) if req.customer_id else False
    tier = _get_escalation_tier(req.crisis_score, on_watchlist, req.customer_arr)
    watchlist_flag = on_watchlist or _watchlist.is_high_arr(req.customer_arr)

    if req.customer_id and _watchlist.is_high_arr(req.customer_arr):
        _watchlist.add(req.customer_id, req.customer_arr)

    if tier in ("red", "watchlist"):
        status = DecisionStatus.PENDING_APPROVAL
        approved_actions: list[str] = []
        blocked_actions = list(req.actions)
    elif tier == "yellow":
        status = DecisionStatus.AUTO_NOTIFY
        approved_actions = list(req.actions)
        blocked_actions = []
    else:
        status = DecisionStatus.AUTO_RESOLVED
        approved_actions = list(req.actions)
        blocked_actions = []

    decision_id = str(uuid.uuid4())
    decision = Decision(
        decision_id=decision_id,
        status=status,
        approved_actions=approved_actions,
        blocked_actions=blocked_actions,
        escalation_tier=tier,
        watchlist_flag=watchlist_flag,
        customer_arr=req.customer_arr,
        crisis_score=req.crisis_score,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    if status == DecisionStatus.PENDING_APPROVAL:
        _pending_store[decision_id] = decision

    return decision


def approve_decision(decision_id: str, approved_by: str = "human_agent") -> Decision | None:
    decision = _pending_store.get(decision_id)
    if not decision:
        return None
    decision.status = DecisionStatus.APPROVED
    decision.resolved_at = datetime.now(timezone.utc).isoformat()
    decision.resolved_by = approved_by
    decision.approved_actions = list(decision.blocked_actions)
    decision.blocked_actions = []
    del _pending_store[decision_id]
    return decision


def reject_decision(
    decision_id: str, rejected_by: str = "human_agent", notes: str = ""
) -> Decision | None:
    decision = _pending_store.get(decision_id)
    if not decision:
        return None
    decision.status = DecisionStatus.REJECTED
    decision.resolved_at = datetime.now(timezone.utc).isoformat()
    decision.resolved_by = rejected_by
    decision.notes = notes
    del _pending_store[decision_id]
    return decision


def list_pending() -> list[Decision]:
    return list(_pending_store.values())


def get_watchlist() -> Watchlist:
    return _watchlist


def clear_state() -> None:
    """Reset module state — used by tests to isolate test runs."""
    _pending_store.clear()
    _watchlist._entries.clear()
