"""Level 2.4 - Official contact / customer-care verification.

Two signals:

* ``l2_contact_intl_prefix``  - a non-Indian dialling code on an India-based role.
  This is one of the highest-signal single features in the job-fraud literature,
  so it fails outright and also feeds a hard floor in the orchestrator.
* ``l2_contact_public_match`` - does the number in the posting match the contact
  the company publishes for itself?
"""

from __future__ import annotations

import re
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.fuzzy_match import similarity
from ..shared.web_search import SearchUnavailable, web_search

LEVEL = 2
LABELS = {
    "l2_contact_intl_prefix": "Contact Number Country Code",
    "l2_contact_public_match": "Public Customer-Care Contact Match",
}

INDIA_DIAL_CODE = "91"
PHONE_RE = re.compile(r"(?:\+|00)(\d{1,3})([\s\-.]?)(\d[\d\s\-.]{6,14}\d)")
BARE_PHONE_RE = re.compile(r"\b([6-9]\d{9})\b")  # Indian mobile without a prefix

INDIA_MARKERS = (
    "india", "indian", "inr", "rupee", "rs.", "rs ", "₹", "mumbai", "delhi",
    "bengaluru", "bangalore", "hyderabad", "chennai", "kolkata", "pune", "noida",
    "gurugram", "gurgaon", "ahmedabad", "kochi", "coimbatore", "jaipur",
)

# Dial codes seen repeatedly in Indian job-scam reports, kept for the finding text.
HIGH_RISK_CODES = {
    "44": "United Kingdom", "60": "Malaysia", "84": "Vietnam", "62": "Indonesia",
    "234": "Nigeria", "233": "Ghana", "63": "Philippines", "66": "Thailand",
    "1": "US/Canada", "971": "UAE", "7": "Russia/Kazakhstan",
}


def check_contact(claims: ExtractedClaims, context: dict[str, Any]) -> list[EvidenceItem]:
    phones = _extract_phones(claims)
    context["posting_phones"] = phones
    return [
        _international_prefix_item(claims, phones, context),
        _public_contact_item(claims, phones, context),
    ]


def _extract_phones(claims: ExtractedClaims) -> list[dict[str, str]]:
    """Every phone number in the posting, with its dial code when stated."""
    sources = [claims.recruiter_phone or "", claims.posting_text or ""]
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    for source in sources:
        for code, separator, rest in PHONE_RE.findall(source):
            national = re.sub(r"\D", "", rest)
            if not separator:
                # Written without a separator ("+919876543210"), so digits leak
                # into the dial-code group: re-split on the 10-digit subscriber
                # number India, the UK and North America all use.
                digits = code + national
                code, national = (digits[:-10], digits[-10:]) if len(digits) > 10 else ("", digits)
            key = f"{code}{national}"
            if key in seen or len(national) < 7:
                continue
            seen.add(key)
            found.append({"dial_code": code, "national": national,
                          "display": f"+{code}-{national}"})
        for national in BARE_PHONE_RE.findall(source):
            key = f"{INDIA_DIAL_CODE}{national}"
            if key in seen:
                continue
            seen.add(key)
            found.append({"dial_code": "", "national": national, "display": national})
    return found


def _india_context(claims: ExtractedClaims) -> bool:
    blob = " ".join(
        filter(None, [claims.location, claims.salary, claims.posting_text])
    ).lower()
    return any(marker in blob for marker in INDIA_MARKERS)


def _international_prefix_item(
    claims: ExtractedClaims, phones: list[dict[str, str]], context: dict[str, Any]
) -> EvidenceItem:
    cid = "l2_contact_intl_prefix"
    if not phones:
        context["intl_contact_flag"] = False
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "The posting carries no phone number, so no dialling code could be checked.",
            raw_data={"phones": []}, confidence=0.0,
        )

    foreign = [p for p in phones if p["dial_code"] and p["dial_code"] != INDIA_DIAL_CODE]
    india_based = _india_context(claims)
    context["intl_contact_flag"] = bool(foreign and india_based)

    if not foreign:
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            f"All {len(phones)} contact number(s) use the Indian dialling code.",
            raw_data={"phones": phones},
        )

    listed = ", ".join(
        f"{p['display']} ({HIGH_RISK_CODES.get(p['dial_code'], 'foreign')})"
        for p in foreign
    )
    if india_based:
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"The role is advertised as India-based but the contact number is "
            f"international: {listed}. Foreign call-back numbers on Indian job "
            "offers are among the strongest fraud indicators on record.",
            raw_data={"phones": phones, "foreign": foreign, "india_based": True},
        )
    return item(
        LEVEL, cid, LABELS[cid], "warning",
        f"The contact number is international ({listed}) and the posting does not "
        "clearly establish which country the role sits in.",
        raw_data={"phones": phones, "foreign": foreign, "india_based": False},
        confidence=0.7,
    )


def _public_contact_item(
    claims: ExtractedClaims, phones: list[dict[str, str]], context: dict[str, Any]
) -> EvidenceItem:
    cid = "l2_contact_public_match"
    company = (claims.company_name or "").strip()
    if not company or not phones:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "A company name and a posting phone number are both needed to compare "
            "against the publicly listed customer-care contact.",
            raw_data={"company_name": company or None, "phones": phones},
            confidence=0.0,
        )

    query = f'"{company}" customer care contact number official'
    try:
        results = web_search(query, max_results=5)
    except SearchUnavailable as exc:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "Web search was unreachable, so the posting's phone number could not be "
            "compared with the company's published contact.",
            raw_data={"query": query, "error": str(exc)}, confidence=0.0,
        )

    context.setdefault("searches", {})[cid] = [r.to_dict() for r in results]
    relevant = [r for r in results if similarity(company, f"{r.title} {r.snippet}") >= 70]
    published: set[str] = set()
    for result in relevant:
        for code, _, rest in PHONE_RE.findall(result.haystack):
            published.add((code + re.sub(r"\D", "", rest))[-10:])
        for national in BARE_PHONE_RE.findall(result.haystack):
            published.add(national[-10:])

    posting_numbers = {p["national"][-10:] for p in phones}
    overlap = posting_numbers & published

    if overlap:
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            "The number in the posting also appears in the company's publicly "
            "listed contact details.",
            raw_data={"query": query, "matched": sorted(overlap)},
        )
    if published:
        return item(
            LEVEL, cid, LABELS[cid], "warning",
            f"{company} publishes a different contact number to the one in this "
            "posting. Recruiters do use direct lines, so this is a mismatch worth "
            "checking rather than proof of fraud.",
            raw_data={"query": query, "posting_numbers": sorted(posting_numbers),
                      "published_numbers": sorted(published)[:5]},
            confidence=0.7,
        )
    return item(
        LEVEL, cid, LABELS[cid], "warning",
        f"No publicly listed customer-care number could be found for {company}, so "
        "the posting's contact number is uncorroborated.",
        raw_data={"query": query, "results": [r.to_dict() for r in results[:3]]},
        confidence=0.6,
    )
