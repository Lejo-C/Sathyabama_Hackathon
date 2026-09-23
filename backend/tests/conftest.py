"""Shared test fixtures.

Every test in this suite runs fully offline: each external call
(``web_search``, ``fetch``, WHOIS, DNS, Groq) is patched per test. Nothing here
touches the network, so the suite passes on stage with the wifi unplugged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.schemas import ExtractedClaims
from app.shared.web_fetch import FetchResult
from app.shared.web_search import SearchResult, SearchUnavailable

FIXTURES = Path(__file__).parent / "fixtures"


def load_claims(name: str) -> ExtractedClaims:
    return ExtractedClaims(**json.loads((FIXTURES / name).read_text(encoding="utf-8")))


@pytest.fixture
def legit_claims() -> ExtractedClaims:
    return load_claims("sample_legit_posting.json")


@pytest.fixture
def scam_claims() -> ExtractedClaims:
    return load_claims("sample_scam_posting.json")


@pytest.fixture
def context() -> dict:
    return {}


def make_results(*rows: tuple[str, str, str]) -> list[SearchResult]:
    """``("title", "url", "snippet")`` tuples into ``SearchResult`` objects."""
    return [SearchResult(title=t, url=u, snippet=s) for t, u, s in rows]


def html_page(body: str, status: int = 200, url: str = "https://example.com") -> FetchResult:
    return FetchResult(
        url=url,
        ok=status < 400,
        status_code=status,
        text=f"<html><body>{body}</body></html>",
        final_url=url,
    )


def dead_page(url: str = "https://example.com", error: str = "ConnectionError: boom") -> FetchResult:
    return FetchResult(url=url, ok=False, error=error)


def offline_search(*_args, **_kwargs):
    raise SearchUnavailable("ConnectionError: network unreachable")


def offline_fetch(url: str = "", *_args, **_kwargs) -> FetchResult:
    return FetchResult(url=url, ok=False, error="ConnectTimeout: network unreachable")


SEARCH_MODULES = (
    "app.level2_company.location_check",
    "app.level2_company.existence_check",
    "app.level2_company.contact_check",
    "app.level3_opportunity.cross_platform_search",
    "app.level4_evidence.review_scraper",
)
FETCH_MODULES = (
    "app.level2_company.location_check",
    "app.level2_company.website_check",
    "app.level3_opportunity.careers_page_check",
    "app.level3_opportunity.payment_flow_detector",
)


@pytest.fixture
def offline(monkeypatch):
    """Cut every external dependency: search, HTTP, WHOIS, DNS and Groq."""
    import importlib

    from app.shared.domain_utils import WhoisUnavailable
    from app.shared.email_utils import DnsUnavailable

    for name in SEARCH_MODULES:
        monkeypatch.setattr(importlib.import_module(name), "web_search", offline_search)
    for name in FETCH_MODULES:
        monkeypatch.setattr(importlib.import_module(name), "fetch", offline_fetch)

    def dead_whois(domain, **kwargs):
        raise WhoisUnavailable("ConnectionError: network unreachable")

    def dead_dns(host, **kwargs):
        raise DnsUnavailable("Timeout: resolver unreachable")

    monkeypatch.setattr("app.level2_company.website_check.domain_age", dead_whois)
    monkeypatch.setattr("app.level2_company.hr_email_check.has_mx", dead_dns)
    for name in ("GROQ_API_KEY", "GROQ_KEY", "VITE_GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return True
