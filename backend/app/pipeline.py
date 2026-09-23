"""Wave-based execution of every Level 2-4 check.

Running the levels one after another cost about 30 seconds, because Level 3 sat
idle waiting for Level 2 and Level 4 waited for Level 3. In practice only two
checks actually depend on an earlier result:

* Level 3.2 (careers page) needs the website Level 2.3 confirmed;
* Level 4.2 (freshness) reuses the listings Level 3.1 collected.

So the work runs in two waves instead of three levels: everything independent
fires at once, then the two dependent checks fire together. Wall clock becomes
roughly "slowest search + slowest fetch" rather than the sum of fifteen calls.
"""

from __future__ import annotations

import logging
from typing import Any

from .core.runner import Check, run_checks
from .core.schemas import EvidenceItem, ExtractedClaims
from .core.scoring import weight
from .level2_company.contact_check import check_contact
from .level2_company.existence_check import check_existence
from .level2_company.hr_email_check import check_hr_email
from .level2_company.location_check import check_location
from .level2_company.website_check import check_website
from .level3_opportunity.careers_page_check import check_careers_page
from .level3_opportunity.cross_platform_search import check_cross_platform
from .level3_opportunity.payment_flow_detector import check_payment_flow
from .level3_opportunity.selection_process_analyzer import check_selection_process
from .level4_evidence.freshness_checker import check_freshness
from .level4_evidence.review_scraper import check_reviews
from .shared import web_search

logger = logging.getLogger(__name__)

# Wave 1: nothing here reads another check's output.
INDEPENDENT_CHECKS: list[Check] = [
    Check("l2_location", "Job Location Verification", 2, weight("l2_location"), check_location),
    Check("l2_company_existence", "Company Existence & Background", 2,
          weight("l2_company_existence"), check_existence),
    Check("l2_website", "Official Website Verification", 2,
          weight("l2_domain_age"), check_website),
    Check("l2_contact", "Official Contact Verification", 2,
          weight("l2_contact_intl_prefix"), check_contact),
    Check("l2_hr_email", "HR Email Verification", 2,
          weight("l2_email_domain_match"), check_hr_email),
    Check("l3_cross_platform", "Cross-Platform Listing Check", 3,
          weight("l3_cross_platform_presence"), check_cross_platform),
    Check("l3_payment_flow", "Payment In Application Flow", 3,
          weight("l3_payment_instrument"), check_payment_flow),
    Check("l3_selection_process", "Recruitment Process Analysis", 3,
          weight("l3_selection_process"), check_selection_process),
    Check("l4_reviews", "Public Reviews & Candidate Experience", 4,
          weight("l4_fraud_mentions"), check_reviews),
]

CAREERS_CHECK = Check(
    "l3_careers_page", "Official Careers Page Listing", 3,
    weight("l3_careers_page"), check_careers_page,
)

# Wave 2: each of these reads context published by wave 1.
DEPENDENT_CHECKS: list[Check] = [
    Check("l4_freshness", "Job Freshness & Repeat Posting", 4,
          weight("l4_repost_pattern"), check_freshness),
]

# Canonical display order of the evidence each level produces, so a parallel run
# still reads top to bottom the way the checks are numbered in the framework.
EVIDENCE_ORDER: list[str] = [
    "l2_location", "l2_company_existence", "l2_domain_age", "l2_website_live",
    "l2_domain_name_match", "l2_contact_intl_prefix", "l2_contact_public_match",
    "l2_email_domain_match", "l2_email_free_provider", "l2_email_mx",
    "l3_cross_platform_presence", "l3_cross_platform_consistency", "l3_careers_page",
    "l3_payment_instrument", "l3_payment_gateway_link", "l3_payment_flow_instruction",
    "l3_selection_process",
    "l4_fraud_mentions", "l4_review_presence", "l4_repost_pattern", "l4_listing_age",
]
_ORDER_INDEX = {check_id: index for index, check_id in enumerate(EVIDENCE_ORDER)}


def _sort_key(item: EvidenceItem) -> tuple[int, str]:
    # Every phrase matched by the selection-process analyser sits where that
    # check sits, then alphabetically among themselves.
    key = "l3_selection_process" if item.check_id.startswith("l3_process_") else item.check_id
    return _ORDER_INDEX.get(key, len(EVIDENCE_ORDER)), item.check_id


def run_all_checks(
    claims: ExtractedClaims, context: dict[str, Any]
) -> dict[int, list[EvidenceItem]]:
    """Run every Level 2-4 check and return its evidence grouped by level."""
    web_search.reset_cache()

    # The careers check only needs a base URL. When the posting already gives
    # one it has no dependency at all, so it joins the first wave instead of
    # waiting a full round of lookups for a website it could have used up front.
    first_wave = list(INDEPENDENT_CHECKS)
    second_wave = list(DEPENDENT_CHECKS)
    (first_wave if claims.website_url else second_wave).append(CAREERS_CHECK)

    evidence = run_checks(first_wave, claims, context)
    evidence += run_checks(second_wave, claims, context)

    grouped: dict[int, list[EvidenceItem]] = {2: [], 3: [], 4: []}
    for item in evidence:
        grouped.setdefault(item.level, []).append(item)
    for level, items in grouped.items():
        items.sort(key=_sort_key)
    return grouped
