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
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

import requests

from .contracts import WebIntelResult

MAX_DOCS = 8
MIN_CONTENT_CHARS = 80
TAVILY_ENDPOINT_BASE = os.getenv("TAVILY_API_BASE_URL", "https://api.tavily.com")
TAVILY_DEFAULT_DEPTH = "advanced"

# 24h in-memory dedup: key = LOWER(company_name), value = (expires_monotonic, result)
_intel_cache: dict[str, tuple[float, WebIntelResult]] = {}
_CACHE_TTL_SECONDS = 86_400  # 24h


class WebIntelError(Exception):
    """Raised when Tavily call fails or returns nothing usable."""


def fetch_web_intel(company_name: str, industry_hint: str | None = None) -> WebIntelResult:
    """Fetch and normalise recent public web context for the target company.

    Returns a WebIntelResult even if zero documents survive filtering — the
    Claude prompt handles the empty case gracefully.
    Degrades silently to an empty result when TAVILY_API_KEY is absent.
    """
    cache_key = company_name.strip().lower()
    now_mono = time.monotonic()

    cached = _intel_cache.get(cache_key)
    if cached is not None and now_mono < cached[0]:
        return cached[1]

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        result = WebIntelResult(query=company_name, fetched_at=_now_iso(), documents=[])
        _intel_cache[cache_key] = (now_mono + _CACHE_TTL_SECONDS, result)
        return result

    queries = _build_queries(company_name, industry_hint)
    seen_urls: set[str] = set()
    documents: list[dict] = []

    for query in queries:
        if len(documents) >= MAX_DOCS:
            break
        try:
            results = _tavily_search(api_key, query)
        except Exception as exc:
            raise WebIntelError(f"Tavily search failed for '{query}': {exc}") from exc

        for r in results:
            url = r.get("url", "").strip()
            content = r.get("content", "").strip()
            if not url or url in seen_urls:
                continue
            if len(content) < MIN_CONTENT_CHARS:
                continue
            seen_urls.add(url)
            documents.append({"url": url, "title": r.get("title", ""), "content": content})
            if len(documents) >= MAX_DOCS:
                break

    result = WebIntelResult(query=company_name, fetched_at=_now_iso(), documents=documents)
    _intel_cache[cache_key] = (now_mono + _CACHE_TTL_SECONDS, result)
    return result


def _build_queries(company_name: str, industry_hint: str | None) -> list[str]:
    base = company_name.strip()
    hint = f" {industry_hint}" if industry_hint else ""
    queries = [
        f"{base} company overview{hint}",
        f"{base} news 2025 2026",
    ]
    sa_keywords = ("bank", "financ", "insurance", "tax", "compliance", "retail", "sarb", "popia")
    hint_lower = (industry_hint or "").lower()
    if any(kw in hint_lower for kw in sa_keywords):
        queries.append(f"{base} POPIA SARB compliance regulatory")
    return queries


def _tavily_search(api_key: str, query: str) -> list[dict[str, Any]]:
    endpoint = f"{TAVILY_ENDPOINT_BASE}/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": TAVILY_DEFAULT_DEPTH,
        "max_results": 5,
        "include_raw_content": False,
    }
    timeout = float(os.getenv("TAVILY_TIMEOUT_SECONDS", "15"))
    resp = requests.post(endpoint, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
