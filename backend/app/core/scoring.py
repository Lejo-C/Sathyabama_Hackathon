"""Deterministic scoring for Levels 2-4.

Everything tunable lives in this file. The LLM never touches a number here;
it only writes prose about the numbers this module produces.

Score direction: **0-100, lower = riskier.** A level starts at 100 and loses
``risk_weight`` points for a failed check (roughly half that for a warning),
scaled by the check's confidence so a half-broken lookup cannot fully condemn
a posting.
"""

from __future__ import annotations

from .schemas import EvidenceItem

# --------------------------------------------------------------------------
# TUNING DIAL - the single place to adjust behaviour during a demo.
# --------------------------------------------------------------------------

CHECK_WEIGHTS: dict[str, float] = {
    # Level 2 - company background
    "l2_location": 10.0,
    "l2_company_existence": 20.0,
    "l2_domain_age": 18.0,
    "l2_website_live": 12.0,
    "l2_domain_name_match": 15.0,
    "l2_contact_intl_prefix": 22.0,
    "l2_contact_public_match": 8.0,
    "l2_email_domain_match": 18.0,
    "l2_email_free_provider": 14.0,
    "l2_email_mx": 16.0,
    # Level 3 - the opportunity itself
    "l3_cross_platform_presence": 14.0,
    "l3_cross_platform_consistency": 16.0,
    "l3_careers_page": 14.0,
    "l3_payment_instrument": 60.0,
    "l3_payment_gateway_link": 25.0,
    "l3_payment_flow_instruction": 30.0,
    "l3_selection_process": 12.0,
    # Level 4 - external evidence
    "l4_fraud_mentions": 45.0,
    "l4_review_presence": 15.0,
    "l4_repost_pattern": 25.0,
    "l4_listing_age": 15.0,
}

# How much of a check's weight is actually charged, per status.
STATUS_PENALTY: dict[str, float] = {
    "fail": 1.0,
    "warning": 0.45,
    "pass": 0.0,
    "unavailable": 0.0,  # "we could not check" is never counted as guilt
}

# Contribution of each level to the combined Level 2-4 score.
LEVEL_WEIGHTS: dict[int, float] = {2: 0.40, 3: 0.35, 4: 0.25}

# Hard ceilings applied after weighted scoring. Keys are flag names set by the
# checks; values are the highest score a posting carrying that flag may hold.
HARD_FLOORS: dict[str, float] = {
    "payment_to_individual": 15.0,
    "new_domain_and_email_mismatch": 25.0,
    "intl_contact_unverified_company": 30.0,
}

HARD_FLOOR_REASONS: dict[str, str] = {
    "payment_to_individual": (
        "A payment instruction to an individual account was confirmed in the "
        "application flow (Level 3.3)."
    ),
    "new_domain_and_email_mismatch": (
        "The company domain is under 30 days old and the recruiter email does "
        "not belong to it (Level 2.3 + Level 2.5)."
    ),
    "intl_contact_unverified_company": (
        "An international phone prefix was used for an India-based role with no "
        "verified company presence (Level 2.4)."
    ),
}

# Fraction of a level's checks that must come back unavailable before the whole
# response is flagged low-confidence.
LOW_CONFIDENCE_RATIO = 0.6


def weight(check_id: str, default: float = 10.0) -> float:
    """Weight for ``check_id``; a missing entry falls back to a modest default."""
    return CHECK_WEIGHTS.get(check_id, default)


def penalty_for(item: EvidenceItem) -> float:
    """Points an individual evidence item removes from its level's score."""
    factor = STATUS_PENALTY.get(item.status, 0.0)
    if factor == 0.0:
        return 0.0
    confidence = item.confidence if item.confidence > 0 else 1.0
    return item.risk_weight * factor * confidence


def score_evidence(evidence: list[EvidenceItem]) -> float:
    """0-100 score for one level's evidence list (lower = riskier)."""
    if not evidence:
        return 100.0
    total_penalty = sum(penalty_for(item) for item in evidence)
    return max(0.0, min(100.0, 100.0 - total_penalty))


def combine_levels(level_scores: dict[int, float]) -> float:
    """Weighted combination of the Level 2/3/4 scores."""
    total_weight = sum(LEVEL_WEIGHTS.get(level, 0.0) for level in level_scores)
    if total_weight <= 0:
        return 100.0
    weighted = sum(
        score * LEVEL_WEIGHTS.get(level, 0.0) for level, score in level_scores.items()
    )
    return max(0.0, min(100.0, weighted / total_weight))


def apply_hard_floors(score: float, flags: dict[str, bool]) -> tuple[float, list[str]]:
    """Cap ``score`` for every raised flag. Returns the capped score and reasons.

    These ceilings are non-negotiable: a strong showing elsewhere cannot lift a
    posting that asked a candidate to pay an individual.
    """
    applied: list[str] = []
    for flag, ceiling in HARD_FLOORS.items():
        if flags.get(flag) and score > ceiling:
            score = ceiling
            applied.append(flag)
        elif flags.get(flag):
            applied.append(flag)
    return max(0.0, min(100.0, score)), applied


def is_low_confidence(evidence: list[EvidenceItem]) -> bool:
    """True when most checks could not reach their external source."""
    if not evidence:
        return True
    unavailable = sum(1 for item in evidence if item.status == "unavailable")
    return unavailable / len(evidence) >= LOW_CONFIDENCE_RATIO
