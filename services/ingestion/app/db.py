import logging
import os
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras

    _PSYCOPG2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PSYCOPG2_AVAILABLE = False


@contextmanager
def get_db() -> Generator:
    """Yield an open psycopg2 connection, or None when DATABASE_URL is not set."""
    url = os.getenv("DATABASE_URL") if _PSYCOPG2_AVAILABLE else None
    if not url:
        yield None
        return
    conn = None
    try:
        conn = psycopg2.connect(url)
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
