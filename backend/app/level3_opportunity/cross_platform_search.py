"""Level 3.1 - Cross-posting check across job platforms.

A genuine vacancy usually leaves a trail on more than one platform, and the
details agree across them. Two signals come out of one search:

* ``l3_cross_platform_presence``    - is the role listed anywhere public?
* ``l3_cross_platform_consistency`` - do the listings agree on salary and title?

Results are cached in the shared context so Level 4.2 can reason about posting
dates without running the same search again.
"""

from __future__ import annotations

import re
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.domain_utils import parse_domain
from ..shared.fuzzy_match import similarity
from ..shared.web_search import SearchResult, SearchUnavailable, web_search

LEVEL = 3
LABELS = {
    "l3_cross_platform_presence": "Cross-Platform Listing Presence",
    "l3_cross_platform_consistency": "Cross-Platform Detail Consistency",
}

JOB_PLATFORMS = {
    "linkedin.com": "LinkedIn",
    "naukri.com": "Naukri",
    "indeed.com": "Indeed",
    "indeed.co.in": "Indeed India",
    "shine.com": "Shine",
    "monsterindia.com": "Monster India",
    "foundit.in": "Foundit",
    "timesjobs.com": "TimesJobs",
    "glassdoor.co.in": "Glassdoor",
    "glassdoor.com": "Glassdoor",
    "internshala.com": "Internshala",
    "apna.co": "Apna",
}

# Two listings whose salaries differ by more than this fraction are treated as
# describing different offers.
SALARY_DIVERGENCE = 0.4
MONEY_RE = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(lpa|lakh|lakhs|k|cr)?", re.I)


def check_cross_platform(
    claims: ExtractedClaims, context: dict[str, Any]
) -> list[EvidenceItem]:
    title = (claims.job_title or "").strip()
    company = (claims.company_name or "").strip()
    if not title or not company:
        context["cross_platform_results"] = []
        reason = (
            "A job title and a company name are both needed to look the role up on "
            "other platforms."
        )
        return [
            item(LEVEL, cid, label, "unavailable", reason,
                 raw_data={"job_title": title or None, "company_name": company or None},
                 confidence=0.0)
            for cid, label in LABELS.items()
        ]

    query = (
        f'"{title}" "{company}" site:linkedin.com OR site:naukri.com '
        f"OR site:indeed.com"
    )
    try:
        results = web_search(query, max_results=8)
        if not results:
            # Some back-ends drop multi-site operators; retry unfiltered and
            # filter locally rather than reporting a false "not listed anywhere".
            results = web_search(f'"{title}" "{company}" job vacancy', max_results=8)
    except SearchUnavailable as exc:
        context["cross_platform_results"] = []
        context["cross_platform_available"] = False
        return [
            item(LEVEL, cid, label, "unavailable",
                 "Web search was unreachable, so cross-platform listings could not "
                 "be checked.",
                 raw_data={"query": query, "error": str(exc)}, confidence=0.0)
            for cid, label in LABELS.items()
        ]

    platform_hits = _platform_hits(results, title, company)
    context["cross_platform_results"] = [hit["result"].to_dict() for hit in platform_hits]
    context["cross_platform_raw"] = [r.to_dict() for r in results]
    context["cross_platform_available"] = True

    return [
        _presence_item(title, company, platform_hits, query),
        _consistency_item(claims, platform_hits),
    ]


def _platform_hits(
    results: list[SearchResult], title: str, company: str
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for result in results:
        domain = parse_domain(result.url).registered_domain
        platform = JOB_PLATFORMS.get(domain)
        if not platform:
            continue
        if similarity(company, result.haystack) < 60:
            continue
        hits.append(
            {
                "platform": platform,
                "url": result.url,
                "title_similarity": round(similarity(title, result.title), 1),
                "result": result,
            }
        )
    return hits


def _presence_item(
    title: str, company: str, hits: list[dict[str, Any]], query: str
) -> EvidenceItem:
    cid = "l3_cross_platform_presence"
    platforms = sorted({hit["platform"] for hit in hits})
    raw = {
        "query": query,
        "platforms": platforms,
        "listings": [{"platform": h["platform"], "url": h["url"]} for h in hits[:5]],
    }

    if not hits:
        return item(
            LEVEL, cid, LABELS[cid], "warning",
            f"'{title}' at {company} is not listed on any mainstream job platform. "
            "An exclusive or brand-new vacancy can look like this too, so it is a "
            "flag rather than proof.",
            raw_data=raw, confidence=0.7,
        )
    return item(
        LEVEL, cid, LABELS[cid], "pass",
        f"The role is listed on {len(platforms)} mainstream platform(s): "
        f"{', '.join(platforms)}.",
        raw_data=raw,
    )


def _consistency_item(
    claims: ExtractedClaims, hits: list[dict[str, Any]]
) -> EvidenceItem:
    cid = "l3_cross_platform_consistency"
    if not hits:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "No other listing of this role was found, so there is nothing to "
            "compare the posting's details against.",
            raw_data={"listings": 0}, confidence=0.0,
        )

    posting_salary = _salary_values(claims.salary or "")
    mismatches: list[dict[str, Any]] = []

    for hit in hits:
        listing_salary = _salary_values(hit["result"].snippet)
        if posting_salary and listing_salary and _diverges(posting_salary, listing_salary):
            mismatches.append(
                {"platform": hit["platform"], "url": hit["url"],
                 "posting_salary": posting_salary, "listing_salary": listing_salary,
                 "field": "salary"}
            )
        elif hit["title_similarity"] < 50:
            mismatches.append(
                {"platform": hit["platform"], "url": hit["url"],
                 "listing_title": hit["result"].title, "field": "job_title"}
            )

    if mismatches:
        fields = sorted({m["field"] for m in mismatches})
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"The same vacancy is advertised with different {', '.join(fields)} on "
            f"{len(mismatches)} other platform(s) - the offer in this posting does "
            "not match the public listing.",
            raw_data={"mismatches": mismatches[:3]}, confidence=0.7,
        )

    return item(
        LEVEL, cid, LABELS[cid], "pass",
        f"Details in this posting are consistent with the {len(hits)} public "
        "listing(s) found.",
        raw_data={"listings": [{"platform": h["platform"], "url": h["url"]} for h in hits[:5]]},
    )


def _salary_values(text: str) -> list[float]:
    """Monthly-rupee equivalents of every salary figure in ``text``."""
    values: list[float] = []
    for amount, unit in MONEY_RE.findall(text or ""):
        try:
            number = float(amount.replace(",", ""))
        except ValueError:
            continue
        unit = (unit or "").lower()
        if unit in {"lpa", "lakh", "lakhs"}:
            number = number * 100_000 / 12
        elif unit == "cr":
            number = number * 10_000_000 / 12
        elif unit == "k":
            number = number * 1_000
        values.append(number)
    return values


def _diverges(left: list[float], right: list[float]) -> bool:
    """True when two salary sets do not overlap within the tolerance band."""
    if not left or not right:
        return False
    lo_l, hi_l = min(left), max(left)
    lo_r, hi_r = min(right), max(right)
    if hi_l >= lo_r and hi_r >= lo_l:  # ranges overlap
        return False
    gap = abs((lo_l + hi_l) / 2 - (lo_r + hi_r) / 2)
    reference = max((lo_l + hi_l) / 2, (lo_r + hi_r) / 2, 1.0)
    return gap / reference > SALARY_DIVERGENCE
