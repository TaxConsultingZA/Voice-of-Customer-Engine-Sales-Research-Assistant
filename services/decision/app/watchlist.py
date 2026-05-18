"""
High-ARR customer watchlist.
Customers on the watchlist are always escalated to PENDING_APPROVAL regardless
of their crisis score, protecting high-value accounts from automated actions.
"""

HIGH_ARR_THRESHOLD = 100_000  # R100,000 — auto-adds to watchlist on first Red/Yellow hit


class Watchlist:
    """In-memory watchlist — backed by the decision engine module singleton."""

    def __init__(self) -> None:
        self._entries: dict[str, float] = {}  # customer_id → ARR

    def add(self, customer_id: str, arr: float) -> None:
        self._entries[customer_id] = arr

    def remove(self, customer_id: str) -> bool:
        return self._entries.pop(customer_id, None) is not None

    def is_on_watchlist(self, customer_id: str) -> bool:
        return customer_id in self._entries

    def is_high_arr(self, arr: float) -> bool:
        return arr >= HIGH_ARR_THRESHOLD

    def list_entries(self) -> dict[str, float]:
        return dict(self._entries)
