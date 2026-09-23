"""Level 3.2 - Official careers-page check.

If the company runs a careers page and this vacancy is absent from it, the
posting is not what it claims to be. If the company has no careers page at all,
that proves nothing - the check reports ``unavailable`` instead of inventing a
warning.
"""

from __future__ import annotations

from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.fuzzy_match import core_tokens, similarity
from ..shared.web_fetch import fetch

LEVEL = 3
CHECK_ID = "l3_careers_page"
LABEL = "Official Careers Page Listing"

CAREER_PATHS = ("/careers", "/career", "/jobs", "/join-us", "/work-with-us",
                "/careers/jobs", "/company/careers")

# A page that mentions these is genuinely a careers page rather than a 200-OK
# catch-all route.
CAREERS_MARKERS = ("career", "job", "vacanc", "opening", "hiring", "we are hiring",
                   "join our team", "apply now")
MIN_TITLE_TOKEN_HITS = 0.6


def check_careers_page(
    claims: ExtractedClaims, context: dict[str, Any]
) -> list[EvidenceItem]:
    base = context.get("website_final_url") or context.get("verified_domain") or claims.website_url
    if not base:
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "unavailable",
                "No company website was confirmed in Level 2, so there is no careers "
                "page to search.",
                raw_data={"reason": "no verified website"}, confidence=0.0,
            )
        ]

    title = (claims.job_title or "").strip()
    base_url = str(base).rstrip("/")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    tried: list[dict[str, Any]] = []
    careers_pages: list[dict[str, Any]] = []
    network_failures = 0

    for path in CAREER_PATHS:
        url = base_url + path
        result = fetch(url)
        if not result.ok:
            tried.append({"url": url, "status": result.status_code, "error": result.error})
            if result.status_code is None:
                network_failures += 1
            continue

        text = result.visible_text
        lowered = text.lower()
        tried.append({"url": url, "status": result.status_code, "chars": len(text)})
        if any(marker in lowered for marker in CAREERS_MARKERS):
            careers_pages.append({"url": url, "text": text})
            if title and _lists_role(text, title):
                return [
                    item(
                        LEVEL, CHECK_ID, LABEL, "pass",
                        f"The company's own careers page lists '{title}' ({url}).",
                        raw_data={"careers_url": url, "job_title": title},
                    )
                ]

    if not careers_pages:
        if network_failures == len(CAREER_PATHS):
            return [
                item(
                    LEVEL, CHECK_ID, LABEL, "unavailable",
                    f"None of the usual careers paths on {base_url} could be reached.",
                    raw_data={"attempts": tried}, confidence=0.0,
                )
            ]
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "unavailable",
                f"{base_url} publishes no careers page at the usual paths, so this "
                "vacancy cannot be cross-checked against it.",
                raw_data={"attempts": tried}, confidence=0.0,
            )
        ]

    if not title:
        return [
            item(
                LEVEL, CHECK_ID, LABEL, "unavailable",
                "A careers page exists but the posting gives no job title to look for.",
                raw_data={"careers_pages": [p["url"] for p in careers_pages]},
                confidence=0.0,
            )
        ]

    return [
        item(
            LEVEL, CHECK_ID, LABEL, "warning",
            f"The company runs a careers page ({careers_pages[0]['url']}) but it does "
            f"not advertise '{title}'. A vacancy missing from the employer's own site "
            "deserves direct confirmation before applying.",
            raw_data={"careers_pages": [p["url"] for p in careers_pages],
                      "job_title": title},
            confidence=0.8,
        )
    ]


def _lists_role(text: str, title: str) -> bool:
    """True when the careers page plausibly advertises ``title``."""
    lowered = text.lower()
    if title.lower() in lowered:
        return True
    tokens = [t for t in core_tokens(title) if len(t) > 2]
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in lowered)
    if hits / len(tokens) >= MIN_TITLE_TOKEN_HITS:
        return True
    return similarity(title, lowered[:8000]) >= 90
