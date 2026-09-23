"""HTTP surface for Levels 2-4.

``POST /api/verify/company-opportunity`` takes the shared ``ExtractedClaims``
contract (Level 1's output) and returns the three level reports plus a combined
score and summary.

``GET /api/verify/health`` probes the external dependencies live, so a demo can
show up front whether the venue network is going to allow search and WHOIS - and
the verification endpoint still works when it does not.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter

from ..core.schemas import (
    DependencyHealth,
    ExtractedClaims,
    HealthResponse,
    VerificationResponse,
)
from ..level2_4_orchestrator import verify_company_opportunity
from ..shared.domain_utils import WhoisUnavailable, domain_age
from ..shared.email_utils import DnsUnavailable, has_mx
from ..shared.web_fetch import fetch
from ..shared.web_search import SearchUnavailable, web_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/verify", tags=["verification"])

HEALTH_TIMEOUT = 5.0
HEALTH_PROBE_DOMAIN = "example.com"


@router.post("/company-opportunity", response_model=VerificationResponse)
async def verify(claims: ExtractedClaims) -> VerificationResponse:
    """Run Level 2, 3 and 4 verification over one job posting's claims."""
    # The checks are synchronous (requests / whois / dnspython), so the whole
    # pipeline is handed to a worker thread and the event loop stays free.
    return await asyncio.to_thread(verify_company_opportunity, claims)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Live reachability of every external dependency Levels 2-4 rely on."""
    probes = await asyncio.gather(
        asyncio.to_thread(_timed, "http", _probe_http),
        asyncio.to_thread(_timed, "web_search", _probe_search),
        asyncio.to_thread(_timed, "whois", _probe_whois),
        asyncio.to_thread(_timed, "dns", _probe_dns),
        asyncio.to_thread(_timed, "groq", _probe_groq),
    )
    degraded = any(not probe.available for probe in probes)
    return HealthResponse(
        status="degraded" if degraded else "ok",
        dependencies=list(probes),
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


def _timed(name: str, fn) -> DependencyHealth:
    started = time.perf_counter()
    try:
        detail = fn()
        available = True
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"[:200]
        available = False
    return DependencyHealth(
        name=name,
        available=available,
        detail=detail,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )


def _probe_http() -> str:
    result = fetch(f"https://{HEALTH_PROBE_DOMAIN}", timeout=HEALTH_TIMEOUT, retries=0)
    if not result.ok:
        raise RuntimeError(result.error or f"HTTP {result.status_code}")
    return f"outbound HTTP works (HTTP {result.status_code})"


def _probe_search() -> str:
    results = web_search("job fraud verification", max_results=1)
    return f"ddgs reachable, {len(results)} result(s)"


def _probe_whois() -> str:
    try:
        age = domain_age(HEALTH_PROBE_DOMAIN, timeout=HEALTH_TIMEOUT)
    except WhoisUnavailable as exc:
        raise RuntimeError(str(exc)) from exc
    return f"whois reachable (probe domain age {age.age_days} days)"


def _probe_dns() -> str:
    try:
        deliverable = has_mx("gmail.com", timeout=HEALTH_TIMEOUT)
    except DnsUnavailable as exc:
        raise RuntimeError(str(exc)) from exc
    return f"DNS resolver reachable (MX lookup returned {deliverable})"


def _probe_groq() -> str:
    """Key presence only - never spends a token just to answer a health check."""
    configured = any(
        os.getenv(name) for name in ("GROQ_API_KEY", "GROQ_KEY", "VITE_GROQ_API_KEY")
    )
    if not configured:
        raise RuntimeError("GROQ_API_KEY not set - explanations fall back to template")
    return "GROQ_API_KEY present; explanations will use Groq with template fallback"
