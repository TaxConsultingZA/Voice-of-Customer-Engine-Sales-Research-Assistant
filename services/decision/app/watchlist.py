"""
High-ARR customer watchlist.
Customers on the watchlist are always escalated to PENDING_APPROVAL regardless
of their crisis score, protecting high-value accounts from automated actions.
"""

import logging

logger = logging.getLogger(__name__)

HIGH_ARR_THRESHOLD = 100_000  # R100,000 — auto-adds to watchlist on first Red/Yellow hit


class Watchlist:
    """In-memory watchlist backed by PostgreSQL for durability."""

    def __init__(self) -> None:
        self._entries: dict[str, float] = {}  # customer_id → ARR

    def add(self, customer_id: str, arr: float) -> None:
        self._entries[customer_id] = arr
        self._db_upsert(customer_id, arr)

    def remove(self, customer_id: str) -> bool:
        removed = self._entries.pop(customer_id, None) is not None
        if removed:
            self._db_delete(customer_id)
        return removed

    def is_on_watchlist(self, customer_id: str) -> bool:
        return customer_id in self._entries

    def is_high_arr(self, arr: float) -> bool:
        return arr >= HIGH_ARR_THRESHOLD

    def list_entries(self) -> dict[str, float]:
        return dict(self._entries)

    # ── PostgreSQL helpers ─────────────────────────────────────────────────────

    def _db_upsert(self, customer_id: str, arr: float) -> None:
        from .db import get_db

        try:
            with get_db() as conn:
                if conn is None:
                    return
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO watchlist (customer_id, arr)
                        VALUES (%s, %s)
                        ON CONFLICT (customer_id) DO UPDATE SET arr = EXCLUDED.arr
                        """,
                        (customer_id, arr),
                    )
        except Exception as exc:
            logger.warning("PostgreSQL watchlist upsert failed for %s: %s", customer_id, exc)

    def _db_delete(self, customer_id: str) -> None:
        from .db import get_db

        try:
            with get_db() as conn:
                if conn is None:
                    return
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM watchlist WHERE customer_id = %s", (customer_id,))
        except Exception as exc:
            logger.warning("PostgreSQL watchlist delete failed for %s: %s", customer_id, exc)
