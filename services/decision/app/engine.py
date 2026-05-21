"""
Decision Intelligence Engine — core decision logic.

Governance gates:
    Green   crisis_score < 0.3                → AUTO_RESOLVED
    Yellow  0.3 ≤ crisis_score < 0.6          → AUTO_NOTIFY
    Red     crisis_score ≥ 0.6                → PENDING_APPROVAL (blocked)
    Watchlist  customer on watchlist OR ARR ≥ R100K  → PENDING_APPROVAL (blocked)

Watchlist customers are auto-enrolled on their first high-ARR signal.
"""

import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from .db import get_db
from .models import Decision, DecisionRequest, DecisionStatus
from .watchlist import HIGH_ARR_THRESHOLD, Watchlist

logger = logging.getLogger(__name__)

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

    _db_persist_decision(decision)
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
    _db_update_decision(decision)
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
    _db_update_decision(decision)
    return decision


def list_pending() -> list[Decision]:
    return list(_pending_store.values())


def get_watchlist() -> Watchlist:
    return _watchlist


def restore_state_from_db() -> None:
    """Reload pending decisions and watchlist from PostgreSQL after a restart."""
    try:
        with get_db() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT decision_id, status, escalation_tier, crisis_score, customer_arr, "
                    "watchlist_flag, approved_actions, blocked_actions, created_at, "
                    "resolved_at, resolved_by, notes "
                    "FROM decisions WHERE status = %s",
                    (DecisionStatus.PENDING_APPROVAL.value,),
                )
                for row in cur.fetchall():
                    d = Decision(
                        decision_id=row[0],
                        status=DecisionStatus(row[1]),
                        escalation_tier=row[2],
                        crisis_score=row[3] or 0.0,
                        customer_arr=row[4] or 0.0,
                        watchlist_flag=bool(row[5]),
                        approved_actions=row[6] or [],
                        blocked_actions=row[7] or [],
                        created_at=row[8].isoformat() if row[8] else "",
                        resolved_at=row[9].isoformat() if row[9] else None,
                        resolved_by=row[10],
                        notes=row[11] or "",
                    )
                    _pending_store[d.decision_id] = d

                cur.execute("SELECT customer_id, arr FROM watchlist")
                for customer_id, arr in cur.fetchall():
                    _watchlist.add(customer_id, arr)

        logger.info(
            "Restored %d pending decisions and %d watchlist entries from PostgreSQL",
            len(_pending_store),
            len(_watchlist.list_entries()),
        )
    except Exception as exc:
        logger.warning("Could not restore state from PostgreSQL: %s", exc)


def clear_state() -> None:
    """Reset module state — used by tests to isolate test runs."""
    _pending_store.clear()
    _watchlist._entries.clear()


# ── PostgreSQL persistence helpers ────────────────────────────────────────────


def _db_persist_decision(decision: Decision) -> None:
    try:
        with get_db() as conn:
            if conn is None:
                return
            import psycopg2.extras

            d = asdict(decision)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO decisions (
                        decision_id, status, escalation_tier, crisis_score, customer_arr,
                        watchlist_flag, approved_actions, blocked_actions,
                        created_at, resolved_at, resolved_by, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (decision_id) DO NOTHING
                    """,
                    (
                        d["decision_id"],
                        d["status"],
                        d["escalation_tier"],
                        d["crisis_score"],
                        d["customer_arr"],
                        d["watchlist_flag"],
                        psycopg2.extras.Json(d["approved_actions"]),
                        psycopg2.extras.Json(d["blocked_actions"]),
                        d["created_at"],
                        d.get("resolved_at"),
                        d.get("resolved_by"),
                        d.get("notes", ""),
                    ),
                )
    except Exception as exc:
        logger.warning("PostgreSQL write failed for decision %s: %s", decision.decision_id, exc)


def _db_update_decision(decision: Decision) -> None:
    try:
        with get_db() as conn:
            if conn is None:
                return
            import psycopg2.extras

            d = asdict(decision)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE decisions
                    SET status = %s,
                        approved_actions = %s,
                        blocked_actions  = %s,
                        resolved_at      = %s,
                        resolved_by      = %s,
                        notes            = %s
                    WHERE decision_id = %s
                    """,
                    (
                        d["status"],
                        psycopg2.extras.Json(d["approved_actions"]),
                        psycopg2.extras.Json(d["blocked_actions"]),
                        d.get("resolved_at"),
                        d.get("resolved_by"),
                        d.get("notes", ""),
                        d["decision_id"],
                    ),
                )
    except Exception as exc:
        logger.warning("PostgreSQL update failed for decision %s: %s", decision.decision_id, exc)
