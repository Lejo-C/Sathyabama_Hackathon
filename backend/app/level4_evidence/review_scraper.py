"""Level 4.1 - Public reviews and candidate experience.

One search, two signals: has anyone publicly reported this employer for fraud,
and does it have a normal employer-review footprint at all? Each result is
classified locally - by its wording for complaints, by its domain for review
sites - so both answers come out of a single round trip.

Copyright discipline: at most one short phrase is quoted per source, always with
its URL, never a reproduced paragraph.
"""

from __future__ import annotations

import re
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.domain_utils import parse_domain
from ..shared.fuzzy_match import similarity
from ..shared.web_search import SearchResult, SearchUnavailable, web_search

LEVEL = 4
LABELS = {
    "l4_fraud_mentions": "Public Fraud / Complaint Reports",
    "l4_review_presence": "Employer Review Footprint",
}

FRAUD_TERMS = (
    "scam", "fraud", "fraudulent", "cheated", "complaint", "duped", "fake job",
    "fake offer", "money back", "police complaint", "fir ", "ripoff", "conned",
)
REVIEW_SITES = {
    "glassdoor.com": "Glassdoor",
    "glassdoor.co.in": "Glassdoor",
    "ambitionbox.com": "AmbitionBox",
    "indeed.com": "Indeed",
    "indeed.co.in": "Indeed",
    "naukri.com": "Naukri",
    "linkedin.com": "LinkedIn",
    "mouthshut.com": "MouthShut",
    "trustpilot.com": "Trustpilot",
    "quora.com": "Quora",
    "reddit.com": "Reddit",
}
COMPANY_RELEVANCE = 70.0
MAX_RESULTS = 8
MAX_QUOTED_WORDS = 8
DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:day|week|month|year)s?\s+ago)\b",
    re.I,
)


def check_reviews(claims: ExtractedClaims, context: dict[str, Any]) -> list[EvidenceItem]:
    company = (claims.company_name or "").strip()
    if not company:
        reason = "The posting names no company, so no reviews or reports can be sought."
        return [
            item(LEVEL, cid, label, "unavailable", reason,
                 raw_data={"reason": "no company name"}, confidence=0.0)
            for cid, label in LABELS.items()
        ]

    # One query answers both questions, and each result is classified locally:
    # complaint reports by their wording, review presence by their domain.
    # Two queries doubled this check's wall-clock cost on a throttled network
    # for evidence the same result set already carries.
    query = f'"{company}" scam OR fraud OR complaint OR reviews'
    results, error = _search(query)
    context.setdefault("searches", {})["l4_reviews"] = [r.to_dict() for r in results]

    return [
        _fraud_item(company, results, query, error),
        _presence_item(company, results, query, error),
    ]


def _search(query: str) -> tuple[list[SearchResult], str | None]:
    """Run one search, returning ``(results, error)`` instead of raising."""
    try:
        return web_search(query, max_results=MAX_RESULTS), None
    except SearchUnavailable as exc:
        return [], str(exc)


def _fraud_item(
    company: str, results: list[SearchResult], query: str, error: str | None
) -> EvidenceItem:
    cid = "l4_fraud_mentions"
    if error is not None:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "Web search was unreachable, so public complaint reports could not be "
            "checked. Absence of a flag here is not a clean bill of health.",
            raw_data={"query": query, "error": error}, confidence=0.0,
        )

    mentions = []
    for result in results:
        if similarity(company, f"{result.title} {result.snippet}") < COMPANY_RELEVANCE:
            continue
        hit_terms = [term.strip() for term in FRAUD_TERMS if term in result.haystack]
        if not hit_terms:
            continue
        domain = parse_domain(result.url).registered_domain
        mentions.append(
            {
                "source": REVIEW_SITES.get(domain, domain),
                "url": result.url,
                "date": _date_hint(result.snippet),
                "terms": hit_terms[:3],
                "quote": _short_quote(result.snippet, hit_terms[0]),
            }
        )

    independent = {m["source"] for m in mentions}
    raw = {"query": query, "mentions": mentions[:3],
           "independent_sources": sorted(independent)}

    if len(independent) >= 2:
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"{len(independent)} independent sources publicly report {company} for "
            f"fraud or unpaid/fake hiring ({', '.join(sorted(independent))}).",
            raw_data=raw,
        )
    if mentions:
        return item(
            LEVEL, cid, LABELS[cid], "warning",
            f"One public source associates {company} with a scam or complaint "
            f"({mentions[0]['source']}). A single report is worth reading before "
            "applying, but is not on its own conclusive.",
            raw_data=raw, confidence=0.8,
        )
    return item(
        LEVEL, cid, LABELS[cid], "pass",
        f"No public scam, fraud or complaint report was found for {company}.",
        raw_data={"query": query, "results_scanned": len(results)},
    )


def _presence_item(
    company: str, results: list[SearchResult], query: str, error: str | None
) -> EvidenceItem:
    cid = "l4_review_presence"
    if error is not None and not results:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "Web search was unreachable, so the employer's review footprint is unknown.",
            raw_data={"query": query, "error": error}, confidence=0.0,
        )

    profiles = []
    for result in results:
        domain = parse_domain(result.url).registered_domain
        site = REVIEW_SITES.get(domain)
        if not site:
            continue
        if similarity(company, f"{result.title} {result.snippet}") < COMPANY_RELEVANCE:
            continue
        profiles.append({"site": site, "url": result.url})

    sites = sorted({p["site"] for p in profiles})
    if sites:
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            f"{company} has a public employee/candidate footprint on "
            f"{', '.join(sites)}.",
            raw_data={"query": query, "profiles": profiles[:4]},
        )
    return item(
        LEVEL, cid, LABELS[cid], "warning",
        f"{company} has no presence on any employer-review site, so no candidate "
        "has publicly described working with them.",
        raw_data={"query": query, "results_scanned": len(results)}, confidence=0.7,
    )


def _short_quote(snippet: str, term: str) -> str:
    """At most a few words around the matched term - never a reproduced passage."""
    words = (snippet or "").split()
    if not words:
        return ""
    lowered = [w.lower() for w in words]
    index = next((i for i, w in enumerate(lowered) if term.strip() in w), 0)
    start = max(0, index - MAX_QUOTED_WORDS // 2)
    return " ".join(words[start:start + MAX_QUOTED_WORDS])


def _date_hint(snippet: str) -> str | None:
    match = DATE_RE.search(snippet or "")
    return match.group(0) if match else None
