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
Degrades silently to no-op when DATABASE_URL is absent (local dev, CI).
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

from .contracts import BriefRecord, SalesBrief

CACHE_TTL_DAYS = int(os.getenv("SALES_BRIEF_CACHE_DAYS", "7"))
CACHE_TTL = timedelta(days=CACHE_TTL_DAYS)


class CacheError(Exception):
    """Raised when the cache backend is unreachable."""


def _get_conn():
    """Return a psycopg2 connection or None when DATABASE_URL is absent."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        import psycopg2
        return psycopg2.connect(db_url)
    except Exception:
        return None


def lookup_cached_brief(company_name: str) -> BriefRecord | None:
    """Return the most recent non-expired brief for this company, or None."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, company_name, ae_email, generated_at, cached_until,
                           confidence, brief_payload, source_urls
                    FROM sales_briefs
                    WHERE LOWER(company_name) = LOWER(%s)
                      AND cached_until > NOW()
                    ORDER BY generated_at DESC
                    LIMIT 1
                    """,
                    (company_name,),
                )
                row = cur.fetchone()
    except Exception:
        return None
    finally:
        conn.close()

    if row is None:
        return None

    row_id, co_name, ae_email, generated_at, cached_until, confidence, brief_payload_raw, source_urls = row
    try:
        brief = SalesBrief.model_validate(
            brief_payload_raw if isinstance(brief_payload_raw, dict) else json.loads(brief_payload_raw)
        )
        return BriefRecord(
            id=str(row_id),
            company_name=co_name,
            ae_email=ae_email,
            generated_at=generated_at.isoformat().replace("+00:00", "Z"),
            cached_until=cached_until.isoformat().replace("+00:00", "Z"),
            confidence=float(confidence),
            brief_payload=brief,
            source_urls=source_urls or [],
        )
    except Exception:
        return None


def store_brief(record: BriefRecord) -> None:
    """Persist a freshly generated brief and set its cached_until horizon.

    Silent no-op on any failure — the brief was already generated and
    returned to the AE; a cache miss on the next request is acceptable.
    """
    conn = _get_conn()
    if conn is None:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sales_briefs
                        (company_name, ae_email, generated_at, cached_until,
                         brief_payload, source_urls, confidence)
                    VALUES (%s, %s, %s::timestamptz, %s::timestamptz, %s::jsonb, %s, %s)
                    """,
                    (
                        record.company_name,
                        record.ae_email,
                        record.generated_at,
                        record.cached_until,
                        json.dumps(record.brief_payload.model_dump()),
                        [str(u) for u in record.source_urls],
                        record.confidence,
                    ),
                )
    except Exception:
        pass
    finally:
        conn.close()
