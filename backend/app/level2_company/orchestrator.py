"""Level 2 orchestrator - company background verification.

Runs the five Level 2 checks in parallel (they touch different external
services, so the level costs about as long as its slowest single lookup) and
folds their evidence into one ``LevelReport``.
"""

from __future__ import annotations

from typing import Any

from ..core.runner import Check, run_checks
from ..core.schemas import ExtractedClaims, LevelReport
from ..core.scoring import score_evidence, weight
from .contact_check import check_contact
from .existence_check import check_existence
from .hr_email_check import check_hr_email
from .location_check import check_location
from .website_check import check_website

LEVEL = 2

CHECKS = [
    Check("l2_location", "Job Location Verification", LEVEL, weight("l2_location"), check_location),
    Check("l2_company_existence", "Company Existence & Background", LEVEL,
          weight("l2_company_existence"), check_existence),
    Check("l2_website", "Official Website Verification", LEVEL,
          weight("l2_domain_age"), check_website),
    Check("l2_contact", "Official Contact Verification", LEVEL,
          weight("l2_contact_intl_prefix"), check_contact),
    Check("l2_hr_email", "HR Email Verification", LEVEL,
          weight("l2_email_domain_match"), check_hr_email),
]


def run_level2(claims: ExtractedClaims, context: dict[str, Any] | None = None) -> LevelReport:
    """Run all Level 2 checks and return the level's report."""
    context = context if context is not None else {}
    evidence = run_checks(CHECKS, claims, context)
    report = LevelReport.from_evidence(LEVEL, evidence, score_evidence(evidence))
    context["level2_report"] = report
    return report
