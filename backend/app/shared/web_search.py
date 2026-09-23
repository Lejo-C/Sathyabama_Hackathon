"""Free web search wrapper (DuckDuckGo via ``ddgs``), with retry and timeout.

No API key, no paid tier. Returns a plain list of dataclasses so that every
caller - and every test - works with simple data instead of a vendor object.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SEARCH_TIMEOUT = 6.0
RETRIES = 1


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


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Run a web search.

    Raises ``SearchUnavailable`` when the network is unreachable. Callers catch
    it and emit an ``unavailable`` evidence item instead of failing the request.
    """

    last_error: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            with _client() as ddgs:
                rows = list(ddgs.text(query, max_results=max_results))
            return [
                SearchResult(
                    title=str(row.get("title", "")),
                    url=str(row.get("href") or row.get("url") or ""),
                    snippet=str(row.get("body") or row.get("snippet") or ""),
                )
                for row in rows
            ]
        except Exception as exc:
            last_error = exc
            logger.debug("search attempt %s failed for %r: %s", attempt + 1, query, exc)

    raise SearchUnavailable(f"{type(last_error).__name__}: {last_error}")
