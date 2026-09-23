"""Level 3 orchestrator - verification of the opportunity itself.

Runs the four Level 3 checks in parallel. It expects Level 2 to have run first,
because the careers-page check reuses the website Level 2 confirmed and the
payment detector reuses the company domain - but it degrades cleanly to
``unavailable`` items if that context is missing.
"""

from __future__ import annotations

from typing import Any

from ..core.runner import Check, run_checks
from ..core.schemas import ExtractedClaims, LevelReport
from ..core.scoring import build_level_report, weight
from .careers_page_check import check_careers_page
from .cross_platform_search import check_cross_platform
from .payment_flow_detector import check_payment_flow
from .selection_process_analyzer import check_selection_process

LEVEL = 3

CHECKS = [
    Check("l3_cross_platform", "Cross-Platform Listing Check", LEVEL,
          weight("l3_cross_platform_presence"), check_cross_platform),
    Check("l3_careers_page", "Official Careers Page Listing", LEVEL,
          weight("l3_careers_page"), check_careers_page),
    Check("l3_payment_flow", "Payment In Application Flow", LEVEL,
          weight("l3_payment_instrument"), check_payment_flow),
    Check("l3_selection_process", "Recruitment Process Analysis", LEVEL,
          weight("l3_selection_process"), check_selection_process),
]


def run_level3(claims: ExtractedClaims, context: dict[str, Any] | None = None) -> LevelReport:
    """Run all Level 3 checks and return the level's report."""
    context = context if context is not None else {}
    evidence = run_checks(CHECKS, claims, context)
    report = build_level_report(LEVEL, evidence)
    context["level3_report"] = report
    return report
