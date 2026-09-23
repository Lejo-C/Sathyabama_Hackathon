"""Free web search wrapper (DuckDuckGo via ``ddgs``), with retry and timeout.

No API key, no paid tier. Returns a plain list of dataclasses so that every
caller - and every test - works with simple data instead of a vendor object.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# DuckDuckGo latency swings hard with the network you are on: 2s on a good
# link, 10s+ when it throttles. The budget is env-tunable so a demo can trade
# evidence for speed on the day without a code change.
SEARCH_TIMEOUT = float(os.getenv("PRAHARI_SEARCH_TIMEOUT", "8"))
# No retry: with every level now running concurrently, a second attempt on a
# throttled connection costs more wall-clock time than the result is worth. A
# failed search degrades its check to "unavailable" at zero penalty.
RETRIES = 0

# Several checks legitimately ask similar questions about the same company. One
# request-scoped cache keeps that at one round trip instead of five.
_cache: dict[str, list["SearchResult"]] = {}
_cache_lock = threading.Lock()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    @property
    def haystack(self) -> str:
        return f"{self.title} {self.snippet} {self.url}".lower()

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


class SearchUnavailable(RuntimeError):
    """Raised when search could not be reached at all (offline / throttled)."""


def _client():
    try:
        from ddgs import DDGS  # ddgs >= 9
    except ImportError:  # pragma: no cover - older package name
        from duckduckgo_search import DDGS  # type: ignore

    return DDGS(timeout=SEARCH_TIMEOUT)


def _run_query(query: str, max_results: int) -> list[dict]:
    """Call the search back-end under a timeout we actually control.

    The client's own ``timeout`` only bounds a single HTTP request; it retries
    across back-ends and can run for fifteen seconds when DuckDuckGo throttles
    us. This wrapper abandons the call at ``SEARCH_TIMEOUT`` and lets the check
    report ``unavailable`` rather than holding up the whole response.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        def _call() -> list[dict]:
            with _client() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        return pool.submit(_call).result(timeout=SEARCH_TIMEOUT)
    except FutureTimeout as exc:
        raise TimeoutError(f"search exceeded {SEARCH_TIMEOUT:.0f}s") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def reset_cache() -> None:
    """Drop cached results. Called once per verification request."""
    with _cache_lock:
        _cache.clear()


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Run a web search, reusing a cached result for an identical query.

    Raises ``SearchUnavailable`` when the network is unreachable. Callers catch
    it and emit an ``unavailable`` evidence item instead of failing the request.
    """

    cache_key = f"{max_results}:{query}"
    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        logger.debug("search cache hit for %r", query)
        return list(cached)

    last_error: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            rows = _run_query(query, max_results)
            results = [
                SearchResult(
                    title=str(row.get("title", "")),
                    url=str(row.get("href") or row.get("url") or ""),
                    snippet=str(row.get("body") or row.get("snippet") or ""),
                )
                for row in rows
            ]
            with _cache_lock:
                _cache[cache_key] = list(results)
            return results
        except Exception as exc:
            last_error = exc
            logger.debug("search attempt %s failed for %r: %s", attempt + 1, query, exc)

    raise SearchUnavailable(f"{type(last_error).__name__}: {last_error}")
