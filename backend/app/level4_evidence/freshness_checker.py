"""Level 4.2 - Job freshness, expiry and repeated-posting detection.

This check deliberately runs **no searches of its own**: it reuses the listings
Level 3.1 already collected. Two signals come out of them:

* ``l4_repost_pattern`` - the same advert text resurfacing across months or
  across many platforms at once, the classic ghost-job / scam-template reuse.
* ``l4_listing_age``    - how old the live listing is.

When the sources carry no date at all, the status is ``unavailable``, not
``warning``. Being honest about what cannot be measured is part of the product.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.domain_utils import parse_domain
from ..shared.fuzzy_match import similarity

LEVEL = 4
LABELS = {
    "l4_repost_pattern": "Repeated / Recycled Posting",
    "l4_listing_age": "Listing Freshness",
}

RELATIVE_RE = re.compile(r"\b(\d{1,3})\+?\s*(day|week|month|year)s?\s+ago\b", re.I)
ABSOLUTE_RE = re.compile(
    r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\b",
    re.I,
)
ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
    start=1,
)}
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}

# A spread this wide between the oldest and newest copy of one advert means the
# posting is being recycled rather than filled.
REPOST_SPREAD_DAYS = 90
STALE_LISTING_DAYS = 180
DUPLICATE_SIMILARITY = 92.0


def check_freshness(claims: ExtractedClaims, context: dict[str, Any]) -> list[EvidenceItem]:
    listings = list(context.get("cross_platform_results") or [])
    if not listings:
        listings = list(context.get("cross_platform_raw") or [])

    if not listings:
        reason = (
            "Level 3.1 found no public listing of this role, so there is no posting "
            "history to measure freshness against."
            if context.get("cross_platform_available")
            else "Cross-platform search was unavailable, so no posting history could "
            "be reused here."
        )
        return [
            item(LEVEL, cid, label, "unavailable", reason,
                 raw_data={"listings": 0}, confidence=0.0)
            for cid, label in LABELS.items()
        ]

    dated = []
    for listing in listings:
        age = _age_days(f"{listing.get('title', '')} {listing.get('snippet', '')}")
        if age is not None:
            dated.append({**listing, "age_days": age})

    return [
        _repost_item(claims, listings, dated),
        _age_item(dated, len(listings)),
    ]


def _repost_item(
    claims: ExtractedClaims, listings: list[dict[str, Any]], dated: list[dict[str, Any]]
) -> EvidenceItem:
    cid = "l4_repost_pattern"
    duplicates = _duplicate_groups(claims, listings)
    raw: dict[str, Any] = {
        "listings_examined": len(listings),
        "dated_listings": len(dated),
        "duplicate_copies": duplicates["copies"],
        "distinct_domains": duplicates["domains"],
    }

    if dated:
        ages = [entry["age_days"] for entry in dated]
        spread = max(ages) - min(ages)
        raw["age_spread_days"] = spread
        raw["oldest_days"] = max(ages)
        raw["newest_days"] = min(ages)
        if spread >= REPOST_SPREAD_DAYS and duplicates["copies"] >= 2:
            return item(
                LEVEL, cid, LABELS[cid], "fail",
                f"The same advert has been reposted over a {spread}-day span across "
                f"{len(duplicates['domains'])} site(s). Recycled listings that never "
                "close are a ghost-job and scam-template signature.",
                raw_data=raw,
            )

    if duplicates["copies"] >= 3:
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"Byte-for-byte copies of this advert appear in {duplicates['copies']} "
            f"listings across {len(duplicates['domains'])} site(s), which is template "
            "reuse rather than genuine hiring.",
            raw_data=raw,
        )
    if duplicates["copies"] == 2:
        return item(
            LEVEL, cid, LABELS[cid], "warning",
            "This advert's text appears near-identically in two separate listings; "
            "employers do syndicate adverts, so this alone is not conclusive.",
            raw_data=raw, confidence=0.7,
        )
    if not dated:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            "None of the public listings carries a posting date, so repeat-posting "
            "behaviour cannot be measured.",
            raw_data=raw, confidence=0.0,
        )
    return item(
        LEVEL, cid, LABELS[cid], "pass",
        "No repeated or recycled copies of this advert were found.",
        raw_data=raw,
    )


def _age_item(dated: list[dict[str, Any]], total_listings: int) -> EvidenceItem:
    cid = "l4_listing_age"
    if not dated:
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            f"None of the {total_listings} public listing(s) exposes a posting date, "
            "so the vacancy's age genuinely cannot be determined.",
            raw_data={"listings_examined": total_listings, "dated_listings": 0},
            confidence=0.0,
        )

    ages = sorted(entry["age_days"] for entry in dated)
    newest, oldest = ages[0], ages[-1]
    raw = {"newest_days": newest, "oldest_days": oldest,
           "dated_listings": len(dated), "listings_examined": total_listings}

    if oldest >= STALE_LISTING_DAYS:
        return item(
            LEVEL, cid, LABELS[cid], "warning",
            f"This vacancy has been advertised for {oldest} days and is still open. "
            "Long-running openings that never close are often collecting applicants "
            "rather than hiring.",
            raw_data=raw, confidence=0.8,
        )
    return item(
        LEVEL, cid, LABELS[cid], "pass",
        f"The listing is current (most recent copy posted {newest} day(s) ago).",
        raw_data=raw,
    )


def _duplicate_groups(
    claims: ExtractedClaims, listings: list[dict[str, Any]]
) -> dict[str, Any]:
    """Count listings whose text is near-identical to the posting under review."""
    posting = (claims.posting_text or "")[:1500]
    copies = 0
    domains: set[str] = set()
    for listing in listings:
        snippet = listing.get("snippet") or ""
        if not snippet:
            continue
        if similarity(posting, snippet) >= DUPLICATE_SIMILARITY:
            copies += 1
            domain = parse_domain(listing.get("url", "")).registered_domain
            if domain:
                domains.add(domain)
    return {"copies": copies, "domains": sorted(domains)}


def _age_days(text: str) -> int | None:
    """Best-effort age in days from a search snippet, or None when undatable."""
    if not text:
        return None

    match = RELATIVE_RE.search(text)
    if match:
        amount, unit = int(match.group(1)), match.group(2).lower()
        return amount * UNIT_DAYS.get(unit, 1)

    now = datetime.now(timezone.utc)
    match = ABSOLUTE_RE.search(text)
    if match:
        day, month, year = int(match.group(1)), MONTHS[match.group(2).lower()[:3]], int(match.group(3))
        try:
            return max(0, (now - datetime(year, month, day, tzinfo=timezone.utc)).days)
        except ValueError:
            return None

    match = ISO_RE.search(text)
    if match:
        try:
            posted = datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                tzinfo=timezone.utc,
            )
            return max(0, (now - posted).days)
        except ValueError:
            return None
    return None
