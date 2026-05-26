"""
Public web intelligence fetcher (Tavily-backed).

Responsibilities:
- Query Tavily for the target company across 2-3 angles (overview, recent news,
  regulatory mentions).
- Normalise responses into a single WebIntelResult bundle.
- Strip duplicate URLs and content shorter than `MIN_CONTENT_CHARS`.
- Cap total token spend per call (`MAX_DOCS = 8`).

Why Tavily not raw scraping: rate-limit / anti-bot / parsing chaos isn't worth
the engineering time for an MVP. Tavily returns clean Markdown per result.

TODO (Wei, Task 1):
- Implement `fetch_web_intel()` against Tavily's /search endpoint.
- Add 24h in-memory de-dup so the same company queried twice in a day uses 1
  Tavily call (Tavily Pro = 10k calls/month — protect that budget).
- Surface Tavily errors as WebIntelError so the pipeline can degrade gracefully.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from .contracts import WebIntelResult

MAX_DOCS = 8
MIN_CONTENT_CHARS = 80
TAVILY_ENDPOINT = os.getenv("TAVILY_API_BASE_URL", "https://api.tavily.com")
TAVILY_DEFAULT_DEPTH = "advanced"


class WebIntelError(Exception):
    """Raised when Tavily call fails or returns nothing usable."""


def fetch_web_intel(company_name: str, industry_hint: str | None = None) -> WebIntelResult:
    """Fetch and normalise recent public web context for the target company.

    Returns a WebIntelResult even if zero documents survive filtering — the
    Claude prompt is responsible for handling the empty case.
    """
    raise NotImplementedError(
        "fetch_web_intel() is a Task 1 deliverable — wire Tavily + 24h cache here."
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
