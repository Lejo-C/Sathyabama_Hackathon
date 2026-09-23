"""Level 2.2 - Company existence and background.

Searches for an independent trace of the company: its own site, an encyclopaedia
entry, a business registry record, or a professional-network company page. The
result is written into the shared context because Level 2.4 and the hard floors
need to know whether the company was corroborated at all.
"""

from __future__ import annotations

from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.domain_utils import parse_domain
from ..shared.fuzzy_match import name_matches_domain, similarity
from ..shared.web_search import SearchResult, SearchUnavailable, web_search

LEVEL = 2
CHECK_ID = "l2_company_existence"
LABEL = "Company Existence & Background"

# Independent sources that constitute real corroboration of a company.
CREDIBLE_SOURCES = {
    "wikipedia.org": "encyclopaedia entry",
    "linkedin.com": "professional network company page",
    "crunchbase.com": "startup registry",
    "bloomberg.com": "financial registry",
    "zaubacorp.com": "MCA/ROC company record",
    "tofler.in": "MCA/ROC company record",
    "indiafilings.com": "MCA/ROC company record",
    "mca.gov.in": "Ministry of Corporate Affairs record",
    "glassdoor.com": "employer review site",
    "glassdoor.co.in": "employer review site",
    "ambitionbox.com": "employer review site",
    "naukri.com": "job platform employer profile",
}

NAME_MATCH_THRESHOLD = 70.0


def check_existence(claims: ExtractedClaims, context: dict[str, Any]) -> list[EvidenceItem]:
    company = (claims.company_name or "").strip()
    if not company:
        context["company_verified"] = False
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "unavailable",
                "The posting names no company, so there is no entity to verify "
                "(missing company name is reported by Level 1).",
                raw_data={"reason": "no company name claimed"},
                confidence=0.0,
            )
        ]

    query = f'"{company}" company official'
    try:
        results = web_search(query, max_results=5)
    except SearchUnavailable as exc:
        context["company_verified"] = None  # unknown, not "false"
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "unavailable",
                "Web search was unreachable, so the company's existence could not "
                "be confirmed or ruled out.",
                raw_data={"query": query, "error": str(exc)},
                confidence=0.0,
            )
        ]

    context.setdefault("searches", {})[CHECK_ID] = [r.to_dict() for r in results]
    relevant = [r for r in results if similarity(company, f"{r.title} {r.snippet}") >= NAME_MATCH_THRESHOLD]
    credible = _credible_hits(company, relevant)
    context["company_verified"] = bool(credible)
    context["company_evidence_sources"] = [hit["source"] for hit in credible]

    if not results or not relevant:
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "fail",
                f"No search result mentions '{company}' as an operating business. "
                "A company with no public footprint at all is a strong fabrication "
                "signal.",
                raw_data={"query": query, "results": [r.to_dict() for r in results[:3]]},
                confidence=0.8 if results else 0.7,
            )
        ]

    if credible:
        descriptions = ", ".join(sorted({hit["source"] for hit in credible}))
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "pass",
                f"'{company}' has an independent public presence ({descriptions}).",
                raw_data={"query": query, "credible_hits": credible[:3]},
            )
        ]

    return [
        item(
            LEVEL, CHECK_ID, LABEL, "warning",
            f"'{company}' appears in search results, but none of them is an "
            "official site, registry record or established profile - the footprint "
            "is thin.",
            raw_data={"query": query, "results": [r.to_dict() for r in relevant[:3]]},
            confidence=0.8,
        )
    ]


def _credible_hits(company: str, results: list[SearchResult]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for result in results:
        info = parse_domain(result.url)
        registered = info.registered_domain
        if not registered:
            continue
        if registered in CREDIBLE_SOURCES:
            hits.append(
                {"source": CREDIBLE_SOURCES[registered], "url": result.url,
                 "title": result.title}
            )
        elif name_matches_domain(company, info.label) >= 85:
            hits.append(
                {"source": "apparent official website", "url": result.url,
                 "title": result.title}
            )
    return hits
