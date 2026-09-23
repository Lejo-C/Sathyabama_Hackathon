"""Level 4 orchestrator - external evidence.

Runs the two Level 4 checks in parallel. The freshness check reuses the listings
Level 3.1 already gathered, so Level 4 should run after Level 3; with no such
context it reports ``unavailable`` rather than guessing.
"""

from __future__ import annotations

from typing import Any

from ..core.runner import Check, run_checks
from ..core.schemas import ExtractedClaims, LevelReport
from ..core.scoring import build_level_report, weight
from .freshness_checker import check_freshness
from .review_scraper import check_reviews

LEVEL = 4

CHECKS = [
    Check("l4_reviews", "Public Reviews & Candidate Experience", LEVEL,
          weight("l4_fraud_mentions"), check_reviews),
    Check("l4_freshness", "Job Freshness & Repeat Posting", LEVEL,
          weight("l4_repost_pattern"), check_freshness),
]


def run_level4(claims: ExtractedClaims, context: dict[str, Any] | None = None) -> LevelReport:
    """Run all Level 4 checks and return the level's report."""
    context = context if context is not None else {}
    evidence = run_checks(CHECKS, claims, context)
    report = build_level_report(LEVEL, evidence)
    context["level4_report"] = report
    return report
