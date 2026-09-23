"""Level 2.1 - Job location verification.

Principle enforced here: **absence of evidence is not evidence of fraud.**
A location nobody can corroborate is a ``warning``. Only a confidently
*contradicted* location - the company demonstrably operating out of a different
city - earns a ``fail``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.fuzzy_match import contains_location, meaningful_location_tokens, similarity
from ..shared.web_fetch import fetch
from ..shared.web_search import SearchUnavailable, web_search

LEVEL = 2
CHECK_ID = "l2_location"
LABEL = "Job Location Verification"

CONTACT_PATHS = ("/contact", "/contact-us", "/about", "/about-us")

# Cities used to detect a *contradiction*: the company is corroborated in a city
# other than the one claimed. Deliberately conservative - a short, unambiguous
# list beats a long list full of words that double as ordinary English.
KNOWN_CITIES = (
    "mumbai", "delhi", "new delhi", "noida", "gurugram", "gurgaon", "bengaluru",
    "bangalore", "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "jaipur",
    "kochi", "coimbatore", "chandigarh", "indore", "lucknow", "bhubaneswar",
    "visakhapatnam", "nagpur", "thiruvananthapuram", "mysuru", "mysore",
)


def check_location(claims: ExtractedClaims, context: dict[str, Any]) -> list[EvidenceItem]:
    if not claims.location:
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "unavailable",
                "The posting states no job location, so there is nothing to verify "
                "(a missing location is a Level 1 completeness signal, not a Level 2 one).",
                raw_data={"reason": "no location claimed"},
                confidence=0.0,
            )
        ]

    tokens = meaningful_location_tokens(claims.location)
    if not tokens:
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "warning",
                f"Location is stated only as '{claims.location}', which names no "
                "verifiable office - remote-only claims cannot be corroborated "
                "against any address.",
                raw_data={"claimed_location": claims.location, "verifiable_tokens": []},
                confidence=0.6,
            )
        ]

    website_item = _verify_against_website(claims, context)
    if website_item is not None:
        return [website_item]
    return [_verify_against_search(claims, context)]


def _verify_against_website(
    claims: ExtractedClaims, context: dict[str, Any]
) -> EvidenceItem | None:
    """Look for the claimed location on the company's own site. None = no site."""
    if not claims.website_url:
        return None

    pages: list[tuple[str, str]] = []
    home = fetch(claims.website_url)
    if home.ok:
        pages.append((home.final_url or claims.website_url, home.visible_text))
        if not contains_location(home.visible_text, claims.location):
            # Contact and about pages are fetched together rather than one after
            # another; an address is as likely to be on any of them.
            base = (home.final_url or claims.website_url).rstrip("/")
            urls = [base + path for path in CONTACT_PATHS]
            with ThreadPoolExecutor(max_workers=len(urls)) as pool:
                for url, page in zip(urls, pool.map(fetch, urls)):
                    if page.ok and page.visible_text:
                        pages.append((url, page.visible_text))

    if not pages:
        return None  # site unreachable - fall back to search rather than guessing

    for url, text in pages:
        if contains_location(text, claims.location):
            return item(
                LEVEL, CHECK_ID, LABEL, "pass",
                f"Claimed location '{claims.location}' appears on the company's own "
                f"site ({url}).",
                raw_data={"claimed_location": claims.location, "corroborating_url": url},
            )

    combined = " ".join(text for _, text in pages).lower()
    other = _contradicting_city(combined, claims.location)
    if other:
        return item(
            LEVEL, CHECK_ID, LABEL, "fail",
            f"The company site lists an office in {other.title()}, not the claimed "
            f"'{claims.location}'.",
            raw_data={
                "claimed_location": claims.location,
                "site_location": other,
                "pages_checked": [url for url, _ in pages],
            },
            confidence=0.8,
        )

    return item(
        LEVEL, CHECK_ID, LABEL, "warning",
        f"The company site does not mention '{claims.location}' anywhere on its "
        "home or contact pages, so the location is uncorroborated.",
        raw_data={
            "claimed_location": claims.location,
            "pages_checked": [url for url, _ in pages],
        },
        confidence=0.7,
    )


def _verify_against_search(
    claims: ExtractedClaims, context: dict[str, Any]
) -> EvidenceItem:
    company = claims.company_name or ""
    query = f"{company} office {claims.location}".strip()
    try:
        results = web_search(query, max_results=5)
    except SearchUnavailable as exc:
        return item(
            LEVEL, CHECK_ID, LABEL, "unavailable",
            "Web search was unreachable, so the job location could not be "
            "corroborated either way.",
            raw_data={"query": query, "error": str(exc)},
            confidence=0.0,
        )

    context.setdefault("searches", {})[CHECK_ID] = [r.to_dict() for r in results]

    tied = [
        r for r in results
        if not company or similarity(company, f"{r.title} {r.snippet}") >= 70
    ]
    corroborating = [r for r in tied if contains_location(r.haystack, claims.location)]
    if corroborating:
        return item(
            LEVEL, CHECK_ID, LABEL, "pass",
            f"Public search results tie {company or 'the company'} to "
            f"'{claims.location}' ({len(corroborating)} of {len(results)} results).",
            raw_data={
                "query": query,
                "corroborating": [r.to_dict() for r in corroborating[:3]],
            },
        )

    combined = " ".join(r.haystack for r in tied)
    other = _contradicting_city(combined, claims.location)
    if other and len(tied) >= 2:
        return item(
            LEVEL, CHECK_ID, LABEL, "fail",
            f"Search results place {company or 'the company'} in {other.title()} "
            f"rather than the claimed '{claims.location}'.",
            raw_data={"query": query, "search_location": other,
                      "results": [r.to_dict() for r in tied[:3]]},
            confidence=0.7,
        )

    return item(
        LEVEL, CHECK_ID, LABEL, "warning",
        f"No public source ties {company or 'this employer'} to '{claims.location}'. "
        "That is missing corroboration, not proof of a false address.",
        raw_data={"query": query, "results": [r.to_dict() for r in results[:3]]},
        confidence=0.7,
    )


def _contradicting_city(haystack: str, claimed: str) -> str | None:
    """Return a city that is clearly present while the claimed one is absent."""
    if contains_location(haystack, claimed):
        return None
    claimed_tokens = set(meaningful_location_tokens(claimed))
    for city in KNOWN_CITIES:
        if city in claimed_tokens or city in claimed.lower():
            continue
        if city in haystack:
            return city
    return None
