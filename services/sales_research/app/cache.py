"""
7-day brief cache backed by `sales_briefs` Postgres table.

Reason for caching at the brief level (not at Tavily / Claude level):
- Tavily Pro caps us at 10k searches/month. One brief = 2-3 searches.
- Claude Sonnet 4.6 is ~$0.04/brief input+output. Five AEs researching the
  same prospect in one week would be five wasted dollars and 10 Tavily calls
  for an identical result.
- Caching the *final brief* also lets us serve sub-second responses on
  repeat queries — important UX, AEs hate waiting 25s twice.

Cache key: LOWER(company_name) + 7-day TTL.
Cache invalidation: explicit `force_refresh=True` flag bubbled from the UI.
"""

from __future__ import annotations

import os
from datetime import timedelta

from .contracts import BriefRecord

CACHE_TTL_DAYS = int(os.getenv("SALES_BRIEF_CACHE_DAYS", "7"))
CACHE_TTL = timedelta(days=CACHE_TTL_DAYS)


class CacheError(Exception):
    """Raised when the cache backend is unreachable."""


def lookup_cached_brief(company_name: str) -> BriefRecord | None:
    """Return the most recent non-expired brief for this company, or None.

    SQL:
        SELECT * FROM sales_briefs
        WHERE LOWER(company_name) = LOWER(%s)
          AND cached_until > NOW()
        ORDER BY generated_at DESC
        LIMIT 1
    """
    raise NotImplementedError("lookup_cached_brief() — Task 1 deliverable (Postgres SELECT).")


def store_brief(record: BriefRecord) -> None:
    """Persist a freshly generated brief and set its cached_until horizon."""
    raise NotImplementedError("store_brief() — Task 1 deliverable (Postgres INSERT).")
