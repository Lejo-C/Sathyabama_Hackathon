"""Thin, defensive HTTP wrapper.

Every outbound call in Levels 2-4 goes through here so that timeouts, retries
and user-agent handling live in exactly one place. Nothing in this module ever
raises: callers get a ``FetchResult`` whose ``ok`` flag tells them whether the
content can be trusted. A hackathon venue with throttled wifi must degrade the
report, not crash the request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EXTERNAL_TIMEOUT = 6.0
RETRIES = 1
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 PRAHARI-verifier/1.0"
)


@dataclass
class FetchResult:
    url: str
    ok: bool
    status_code: int | None = None
    text: str = ""
    final_url: str | None = None
    error: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def visible_text(self) -> str:
        """HTML stripped down to readable text (empty string when not HTML)."""
        if not self.text:
            return ""
        try:
            soup = BeautifulSoup(self.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            return " ".join(soup.get_text(" ").split())
        except Exception:  # pragma: no cover - parser should not take us down
            return self.text

    def links(self) -> list[str]:
        if not self.text:
            return []
        try:
            soup = BeautifulSoup(self.text, "html.parser")
            return [a.get("href", "") for a in soup.find_all("a") if a.get("href")]
        except Exception:  # pragma: no cover
            return []


def fetch(
    url: str,
    timeout: float = EXTERNAL_TIMEOUT,
    retries: int = RETRIES,
    allow_redirects: bool = True,
) -> FetchResult:
    """GET ``url`` with a hard timeout, returning a result object, never raising."""

    if not url:
        return FetchResult(url=url, ok=False, error="empty url")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    last_error = "unknown error"
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"},
                allow_redirects=allow_redirects,
            )
            return FetchResult(
                url=url,
                ok=response.status_code < 400,
                status_code=response.status_code,
                text=response.text or "",
                final_url=response.url,
                headers=dict(response.headers),
            )
        except Exception as exc:  # network error, TLS failure, DNS failure, timeout
            last_error = f"{type(exc).__name__}: {exc}"
            logger.debug("fetch attempt %s failed for %s: %s", attempt + 1, url, exc)

    return FetchResult(url=url, ok=False, error=last_error)
