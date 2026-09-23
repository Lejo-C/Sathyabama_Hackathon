"""Level 2.3 - Official website verification.

Three independent signals come out of one website:

* ``l2_domain_age``        - how long the domain has existed (WHOIS)
* ``l2_website_live``      - does it resolve, and does its content match the company
* ``l2_domain_name_match`` - is the domain actually the company's, or a typosquat

Domain age is a flag, not a verdict: scam corpora are full of domains registered
days before the campaign, but so are legitimate new businesses. That is why a
young domain only caps the score when it is paired with an email mismatch
(see the hard floors in the orchestrator).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.domain_utils import WhoisUnavailable, domain_age, parse_domain
from ..shared.fuzzy_match import core_tokens, name_matches_domain, similarity
from ..shared.web_fetch import fetch

logger = logging.getLogger(__name__)

LEVEL = 2
LABELS = {
    "l2_domain_age": "Domain Age",
    "l2_website_live": "Website Reachability & Content",
    "l2_domain_name_match": "Domain / Company Name Match",
}

NEW_DOMAIN_FAIL_DAYS = 30
NEW_DOMAIN_WARN_DAYS = 90
# rapidfuzz ratio below this means the domain does not plausibly belong to the
# company named in the posting (typosquat or unrelated domain).
TYPOSQUAT_FAIL_RATIO = 85.0
PARKED_PAGE_CHARS = 200

# Fetch failures that mean "this domain does not exist", as opposed to "our
# network is having a bad day".
DEAD_DOMAIN_MARKERS = (
    "nameresolutionerror", "gaierror", "name or service not known",
    "getaddrinfo failed", "nxdomain", "no address associated",
)


def check_website(claims: ExtractedClaims, context: dict[str, Any]) -> list[EvidenceItem]:
    if not claims.website_url:
        context["verified_domain"] = None
        context["domain_age_days"] = None
        reason = (
            "The posting lists no company website, so domain checks cannot run "
            "(a missing website is reported by Level 1 as missing company info)."
        )
        return [
            item(LEVEL, cid, label, "unavailable", reason,
                 raw_data={"reason": "no website_url in claims"}, confidence=0.0)
            for cid, label in LABELS.items()
        ]

    info = parse_domain(claims.website_url)
    if not info.is_valid:
        context["verified_domain"] = None
        return [
            item(LEVEL, "l2_domain_name_match", LABELS["l2_domain_name_match"], "fail",
                 f"'{claims.website_url}' is not a parseable domain.",
                 raw_data={"website_url": claims.website_url}),
        ]

    domain = info.registered_domain
    context["claimed_domain"] = domain

    # WHOIS and the HTTP fetch ask different servers, so they go out together
    # rather than one after the other.
    with ThreadPoolExecutor(max_workers=2) as pool:
        age_future = pool.submit(_domain_age_item, domain, context)
        live_future = pool.submit(_liveness_items, claims, domain, context)
        age_item, live_items = age_future.result(), live_future.result()

    return [age_item, *live_items, _name_match_item(claims, info.label, domain)]


def _domain_age_item(domain: str, context: dict[str, Any]) -> EvidenceItem:
    cid = "l2_domain_age"
    try:
        age = domain_age(domain)
    except WhoisUnavailable as exc:
        context["domain_age_days"] = None
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            f"WHOIS for {domain} could not be read, so the domain's age is unknown.",
            raw_data={"domain": domain, "error": str(exc)}, confidence=0.0,
        )

    context["domain_age_days"] = age.age_days
    if age.age_days is None:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            f"WHOIS for {domain} returned no creation date (the registry redacts it).",
            raw_data=age.to_dict(), confidence=0.0,
        )

    if age.age_days < NEW_DOMAIN_FAIL_DAYS:
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"{domain} was registered {age.age_days} days ago. Domains created "
            "weeks before a hiring campaign are a hallmark of throwaway scam "
            "infrastructure.",
            raw_data=age.to_dict(),
        )
    if age.age_days < NEW_DOMAIN_WARN_DAYS:
        return item(
            LEVEL, cid, LABELS[cid], "warning",
            f"{domain} is only {age.age_days} days old. That is a flag, not proof - "
            "legitimate new businesses also register recently.",
            raw_data=age.to_dict(),
        )
    return item(
        LEVEL, cid, LABELS[cid], "pass",
        f"{domain} has been registered for {age.age_days} days "
        f"({age.age_days // 365} year(s)), consistent with an established employer.",
        raw_data=age.to_dict(),
    )


def _liveness_items(
    claims: ExtractedClaims, domain: str, context: dict[str, Any]
) -> list[EvidenceItem]:
    cid = "l2_website_live"
    result = fetch(claims.website_url or domain)

    if not result.ok:
        error = (result.error or "").lower()
        context["website_reachable"] = False
        if any(marker in error for marker in DEAD_DOMAIN_MARKERS):
            return [
                item(
                    LEVEL, cid, LABELS[cid], "fail",
                    f"{domain} does not resolve at all - the website quoted in the "
                    "posting does not exist.",
                    raw_data={"domain": domain, "error": result.error},
                )
            ]
        if result.status_code and result.status_code >= 400:
            return [
                item(
                    LEVEL, cid, LABELS[cid], "fail",
                    f"{domain} returned HTTP {result.status_code}; the advertised "
                    "company site is not serving content.",
                    raw_data={"domain": domain, "status_code": result.status_code},
                    confidence=0.8,
                )
            ]
        return [
            item(
                LEVEL, cid, LABELS[cid], "unavailable",
                f"{domain} could not be reached from here "
                f"({result.error or 'network error'}); this may be our network.",
                raw_data={"domain": domain, "error": result.error}, confidence=0.0,
            )
        ]

    text = result.visible_text
    context["website_reachable"] = True
    context["verified_domain"] = domain
    context["website_text"] = text[:20000]
    context["website_final_url"] = result.final_url

    if len(text) < PARKED_PAGE_CHARS:
        return [
            item(
                LEVEL, cid, LABELS[cid], "fail",
                f"{domain} resolves but serves an empty or parked page "
                f"({len(text)} characters of text).",
                raw_data={"domain": domain, "status_code": result.status_code,
                          "text_length": len(text)},
            )
        ]

    company = claims.company_name or ""
    if company and not _mentions_company(text, company):
        return [
            item(
                LEVEL, cid, LABELS[cid], "warning",
                f"{domain} is live but its content never names '{company}', so the "
                "site and the posting may not describe the same business.",
                raw_data={"domain": domain, "status_code": result.status_code,
                          "text_length": len(text)},
                confidence=0.8,
            )
        ]

    return [
        item(
            LEVEL, cid, LABELS[cid], "pass",
            f"{domain} is live (HTTP {result.status_code}) and its content matches "
            f"{company or 'the advertised business'}.",
            raw_data={"domain": domain, "status_code": result.status_code,
                      "text_length": len(text)},
        )
    ]


def _mentions_company(text: str, company: str) -> bool:
    """True when the page names the business.

    Compares the distinctive tokens rather than the full legal name: a real
    company site says "Zoho", not "Zoho Corporation Private Limited", on every
    page, and punishing that would be a false positive.
    """
    lowered = text.lower()
    if company.lower() in lowered:
        return True
    tokens = [token for token in core_tokens(company) if len(token) > 2]
    if tokens and all(token in lowered for token in tokens):
        return True
    return similarity(company, text[:4000]) >= 90


def _name_match_item(claims: ExtractedClaims, label: str, domain: str) -> EvidenceItem:
    cid = "l2_domain_name_match"
    company = (claims.company_name or "").strip()
    if not company:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "No company name was supplied, so the domain cannot be matched against it.",
            raw_data={"domain": domain}, confidence=0.0,
        )

    ratio = name_matches_domain(company, label)
    raw = {"domain": domain, "domain_label": label, "company_name": company,
           "match_ratio": round(ratio, 1), "threshold": TYPOSQUAT_FAIL_RATIO}

    if ratio >= TYPOSQUAT_FAIL_RATIO:
        return item(LEVEL, cid, LABELS[cid], "pass",
                    f"Domain '{domain}' matches the company name (similarity "
                    f"{ratio:.0f}/100).", raw_data=raw)
    return item(
        LEVEL, cid, LABELS[cid], "fail",
        f"Domain '{domain}' does not match '{company}' (similarity {ratio:.0f}/100, "
        f"threshold {TYPOSQUAT_FAIL_RATIO:.0f}) - consistent with a lookalike or "
        "borrowed domain.",
        raw_data=raw,
    )
