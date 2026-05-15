"""
Decision Intelligence — data models.
"""

from dataclasses import dataclass, field
from enum import Enum


class DecisionStatus(str, Enum):
    AUTO_RESOLVED = "auto_resolved"  # Green gate — fully automated
    AUTO_NOTIFY = "auto_notify"  # Yellow gate — automated with notification
    PENDING_APPROVAL = "pending_approval"  # Red/watchlist gate — blocked awaiting human
    APPROVED = "approved"  # Human approved the blocked actions
    REJECTED = "rejected"  # Human rejected — no actions taken


@dataclass
class DecisionRequest:
    text: str
    crisis_score: float
    intent: str = "complaint"
    taxonomy_path: str = ""
    customer_id: str = ""
    customer_arr: float = 0.0
    actions: list[str] = field(default_factory=list)
    routing: list[str] = field(default_factory=list)
    sentiment_polarity: float = 0.0


@dataclass
class Decision:
    decision_id: str
    status: DecisionStatus
    approved_actions: list[str]
    blocked_actions: list[str]
    escalation_tier: str  # green | yellow | red | watchlist
    watchlist_flag: bool
    customer_arr: float
    crisis_score: float
    created_at: str
    resolved_at: str | None = None
    resolved_by: str | None = None
    notes: str = ""
