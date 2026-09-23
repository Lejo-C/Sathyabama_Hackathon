"""Top orchestrator for Levels 2, 3 and 4 of the PRAHARI framework.

Pipeline
--------
1. **Level 2** (company background) runs first: its checks execute in parallel
   and publish the verified domain, domain age and email verdicts into a shared
   context.
2. **Level 3** (the opportunity) runs next, reusing the confirmed website for
   the careers-page check.
3. **Level 4** (external evidence) runs last, reusing Level 3's cross-platform
   listings instead of repeating the search.

Scoring is deterministic end to end. Groq is called exactly once, at the very
end, to phrase the finished result in plain English - it cannot alter a number.

Level 1 (poster/text analysis) is a separate teammate module. It merges with
this report in the shared final orchestrator, one level above this file; its
signals are never recomputed here.

Tuning: every weight, level weighting and hard-floor ceiling lives in
``app/core/scoring.py`` and is re-exported below so a demo can be tuned from one
place.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .core.schemas import EvidenceItem, ExtractedClaims, LevelReport, VerificationResponse
from .core.scoring import (  # re-exported: the single tuning surface
    CHECK_WEIGHTS,
    HARD_FLOOR_REASONS,
    HARD_FLOORS,
    LEVEL_WEIGHTS,
    apply_hard_floors,
    combine_levels,
    is_low_confidence,
)
from .level2_company.orchestrator import run_level2
from .level3_opportunity.orchestrator import run_level3
from .level4_evidence.orchestrator import run_level4
from .shared.explainer import explain

logger = logging.getLogger(__name__)

__all__ = [
    "CHECK_WEIGHTS",
    "LEVEL_WEIGHTS",
    "HARD_FLOORS",
    "verify_company_opportunity",
    "collect_hard_floor_flags",
]


def collect_hard_floor_flags(context: dict[str, Any]) -> dict[str, bool]:
    """Translate the shared context into the flags the hard floors act on.

    * ``payment_to_individual``           - Level 3.3 confirmed a payment instrument.
    * ``new_domain_and_email_mismatch``   - Level 2.3 + Level 2.5 together.
    * ``intl_contact_unverified_company`` - Level 2.4 with no verified company.
    """
    domain_age_days = context.get("domain_age_days")
    return {
        "payment_to_individual": bool(context.get("payment_to_individual")),
        "new_domain_and_email_mismatch": bool(
            domain_age_days is not None
            and domain_age_days < 30
            and context.get("email_domain_mismatch")
        ),
        "intl_contact_unverified_company": bool(
            context.get("intl_contact_flag") and not context.get("company_verified")
        ),
    }


def verify_company_opportunity(
    claims: ExtractedClaims, context: dict[str, Any] | None = None
) -> VerificationResponse:
    """Run Levels 2-4 end to end and return the combined, explained report.

    Always returns a valid response. Every external lookup can fail and the
    worst outcome is a low-confidence report built from the offline rule-based
    signals that remain.
    """
    started = time.perf_counter()
    context = context if context is not None else {}

    level2 = _safe_level(2, run_level2, claims, context)
    level3 = _safe_level(3, run_level3, claims, context)
    level4 = _safe_level(4, run_level4, claims, context)

    evidence: list[EvidenceItem] = [
        *level2.evidence, *level3.evidence, *level4.evidence
    ]
    combined = combine_levels(
        {2: level2.level_score, 3: level3.level_score, 4: level4.level_score}
    )
    flags = collect_hard_floor_flags(context)
    combined, applied = apply_hard_floors(combined, flags)
    low_confidence = is_low_confidence(evidence)

    summary, source = explain(evidence, combined, claims.company_name)
    if applied:
        summary = f"{summary} {_floor_note(applied)}"
    if low_confidence:
        summary = (
            f"{summary} Most external lookups were unreachable during this run, so "
            "this score rests on offline rule-based signals only and should be "
            "treated as provisional."
        )

    return VerificationResponse(
        level2=level2,
        level3=level3,
        level4=level4,
        combined_score=round(combined, 2),
        combined_risk_score=round(100.0 - combined, 2),
        combined_summary=summary,
        processing_time_ms=int((time.perf_counter() - started) * 1000),
        hard_floors_applied=applied,
        low_confidence=low_confidence,
        explainer_source=source,
    )


def _safe_level(level: int, runner, claims: ExtractedClaims, context: dict[str, Any]) -> LevelReport:
    """Run one level; an unexpected crash degrades that level, not the request."""
    try:
        return runner(claims, context)
    except Exception as exc:  # pragma: no cover - run_checks already isolates checks
        logger.exception("level %s orchestrator failed", level)
        return LevelReport.from_evidence(
            level,
            [
                EvidenceItem(
                    level=level,
                    check_id=f"l{level}_orchestrator",
                    label=f"Level {level} Verification",
                    status="unavailable",
                    finding=f"Level {level} could not run: {type(exc).__name__}.",
                    raw_data={"error": str(exc)},
                    risk_weight=0.0,
                    confidence=0.0,
                )
            ],
            100.0,
        )


def _floor_note(applied: list[str]) -> str:
    reasons = " ".join(HARD_FLOOR_REASONS.get(flag, "") for flag in applied).strip()
    return f"The score is capped by a mandatory risk ceiling: {reasons}"
