"""Deterministic, priority-driven scoring.

Everything tunable lives in this file. The LLM never touches a number here; it
only writes prose about the numbers this module produces.

Two directions, one truth
-------------------------
Internally each level holds a **safety score**: 0-100, starting at 100 and
losing points, so lower = riskier. The candidate-facing number is its mirror,
the **risk score** (``100 - safety``), where higher = riskier - the direction
the dashboard already uses.

Priority decides the points
---------------------------
Every check declares a priority tier, and the tier sets how many points a
failure removes. That keeps "why is this posting risky?" answerable in one
vocabulary: a *critical* check failing costs 45 points, a *low* one costs 8, and
the breakdown the UI renders is literally those numbers as percentages.
"""

from __future__ import annotations

from .schemas import Contributor, EvidenceItem, LevelReport, Priority, RiskBand

# --------------------------------------------------------------------------
# TUNING DIAL - the single place to adjust behaviour during a demo.
# --------------------------------------------------------------------------

# Points a failed check removes from its level's 100-point safety score.
PRIORITY_POINTS: dict[Priority, float] = {
    "critical": 45.0,
    "high": 22.0,
    "medium": 14.0,
    "low": 8.0,
}

# Priority of every check. This is the primary dial: change a tier and the
# weight, the breakdown percentages and the UI severity badge all follow.
CHECK_PRIORITY: dict[str, Priority] = {
    # Level 2 - company background
    "l2_location": "medium",
    "l2_company_existence": "high",
    "l2_domain_age": "high",
    "l2_website_live": "medium",
    "l2_domain_name_match": "high",
    "l2_contact_intl_prefix": "critical",
    "l2_contact_public_match": "low",
    "l2_email_domain_match": "high",
    "l2_email_free_provider": "high",
    "l2_email_mx": "high",
    # Level 3 - the opportunity itself
    "l3_cross_platform_presence": "medium",
    "l3_cross_platform_consistency": "high",
    "l3_careers_page": "medium",
    "l3_payment_instrument": "critical",
    "l3_payment_gateway_link": "high",
    "l3_payment_flow_instruction": "critical",
    "l3_selection_process": "medium",
    # Level 4 - external evidence
    "l4_fraud_mentions": "critical",
    "l4_review_presence": "low",
    "l4_repost_pattern": "medium",
    "l4_listing_age": "low",
}

# Checks whose weight is deliberately not the plain tier value. A confirmed
# payee handle should sink Level 3 on its own, so it is charged above tier.
CHECK_WEIGHT_OVERRIDES: dict[str, float] = {
    "l3_payment_instrument": 60.0,
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

# Split of the final verdict between the teammate's Level 1 text analysis and
# this module's external verification. External evidence carries more because a
# scammer controls their own wording but not WHOIS, DNS or public complaints.
LEVEL1_WEIGHT = 0.40
LEVELS_2_4_WEIGHT = 0.60

# Risk bands, read off the candidate-facing risk score (higher = riskier).
RISK_BANDS: list[tuple[float, RiskBand, str, str]] = [
    (25.0, "LOW", "LOW RISK",
     "No blocking signal found. Still verify the recruiter through the company's "
     "official channel before sharing documents."),
    (50.0, "MEDIUM", "MEDIUM RISK",
     "Some claims could not be corroborated. Confirm the role directly with the "
     "company before applying, and never pay anything."),
    (75.0, "HIGH", "HIGH RISK",
     "Multiple verification checks failed. Do not send documents or money; "
     "contact the company through its official website to confirm the vacancy."),
    (101.0, "CRITICAL", "CRITICAL RISK",
     "This posting shows the documented pattern of a job scam. Do not apply, do "
     "not pay, and report the listing to the platform it appeared on."),
]

# Hard ceilings applied to the final safety score. Keys are flag names set by
# the checks; values are the highest safety score a posting carrying that flag
# may hold (so a ceiling of 15 means a risk score of at least 85).
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


def priority_for(check_id: str, default: Priority = "medium") -> Priority:
    """Priority tier for ``check_id``."""
    return CHECK_PRIORITY.get(check_id, default)


def weight(check_id: str, default: float = 14.0) -> float:
    """Points ``check_id`` removes when it fails outright."""
    if check_id in CHECK_WEIGHT_OVERRIDES:
        return CHECK_WEIGHT_OVERRIDES[check_id]
    if check_id in CHECK_PRIORITY:
        return PRIORITY_POINTS[CHECK_PRIORITY[check_id]]
    return default


# Derived view of the dial, handy for docs, tests and demo tuning screens.
CHECK_WEIGHTS: dict[str, float] = {
    check_id: weight(check_id) for check_id in CHECK_PRIORITY
}


def penalty_for(item: EvidenceItem) -> float:
    """Points an individual evidence item removes from its level's score."""
    factor = STATUS_PENALTY.get(item.status, 0.0)
    if factor == 0.0:
        return 0.0
    confidence = item.confidence if item.confidence > 0 else 1.0
    return item.risk_weight * factor * confidence


def score_evidence(evidence: list[EvidenceItem]) -> float:
    """0-100 safety score for one level's evidence list (lower = riskier)."""
    if not evidence:
        return 100.0
    total_penalty = sum(penalty_for(item) for item in evidence)
    return max(0.0, min(100.0, 100.0 - total_penalty))


def build_contributors(
    evidence: list[EvidenceItem], scale: float = 1.0, total_points: float | None = None
) -> list[Contributor]:
    """Turn scored evidence into the ordered "why" breakdown.

    ``scale`` weights the points by the level's share of the final verdict, so
    contributors from different levels stay comparable. ``total_points`` lets a
    caller normalise percentages across several levels at once.
    """
    scored = [(item, penalty_for(item) * scale) for item in evidence]
    scored = [(item, points) for item, points in scored if points > 0]
    denominator = total_points if total_points is not None else sum(p for _, p in scored)

    contributors = [
        Contributor(
            check_id=item.check_id,
            title=item.label,
            level=item.level,
            priority=item.priority,
            status=item.status,
            points=round(points, 2),
            percentage=round(100.0 * points / denominator, 1) if denominator else 0.0,
            finding=item.finding,
        )
        for item, points in scored
    ]
    contributors.sort(key=lambda c: c.points, reverse=True)
    return contributors


def describe_basis(evidence: list[EvidenceItem], level_score: float) -> str:
    """One line stating exactly how a level arrived at its score."""
    if not evidence:
        return "No checks ran for this level."

    statuses = [item.status for item in evidence]
    deducted = round(100.0 - level_score, 1)
    drivers = sorted(
        (item for item in evidence if item.points > 0),
        key=lambda item: item.points,
        reverse=True,
    )[:3]
    lead = (
        "; ".join(f"{item.label} ({item.priority}, -{item.points:g})" for item in drivers)
        or "no check deducted points"
    )
    return (
        f"{len(evidence)} checks: {statuses.count('pass')} passed, "
        f"{statuses.count('fail')} failed, {statuses.count('warning')} warned, "
        f"{statuses.count('unavailable')} unavailable. "
        f"{deducted:g} of 100 points deducted, led by {lead}."
    )


def build_level_report(level: int, evidence: list[EvidenceItem]) -> LevelReport:
    """Score one level and attach its breakdown, in one place."""
    for item in evidence:
        item.points = round(penalty_for(item), 2)
    level_score = score_evidence(evidence)
    return LevelReport.from_evidence(
        level,
        evidence,
        level_score,
        contributors=build_contributors(evidence),
        basis=describe_basis(evidence, level_score),
    )


def combine_levels(level_scores: dict[int, float]) -> float:
    """Weighted combination of the Level 2/3/4 safety scores."""
    total_weight = sum(LEVEL_WEIGHTS.get(level, 0.0) for level in level_scores)
    if total_weight <= 0:
        return 100.0
    weighted = sum(
        score * LEVEL_WEIGHTS.get(level, 0.0) for level, score in level_scores.items()
    )
    return max(0.0, min(100.0, weighted / total_weight))


def final_level_shares(include_level1: bool) -> dict[int, float]:
    """Share of the final verdict each level holds, summing to 1.0.

    Without a Level 1 report the 40% it would have held is redistributed across
    Levels 2-4 rather than silently treated as a clean bill of health.
    """
    l24_total = sum(LEVEL_WEIGHTS.values())
    l24_budget = LEVELS_2_4_WEIGHT if include_level1 else 1.0
    shares = {
        level: l24_budget * weight_ / l24_total
        for level, weight_ in LEVEL_WEIGHTS.items()
    }
    if include_level1:
        shares[1] = LEVEL1_WEIGHT
    return shares


def combine_final(
    level_scores: dict[int, float], include_level1: bool
) -> float:
    """Weighted safety score across every level supplied, 0-100."""
    shares = final_level_shares(include_level1)
    usable = {level: score for level, score in level_scores.items() if level in shares}
    total = sum(shares[level] for level in usable)
    if total <= 0:
        return 100.0
    return max(
        0.0,
        min(100.0, sum(score * shares[level] for level, score in usable.items()) / total),
    )


def band_for(risk_score: float) -> tuple[RiskBand, str, str]:
    """``(band, label, recommendation)`` for a candidate-facing risk score."""
    for ceiling, band, label, recommendation in RISK_BANDS:
        if risk_score < ceiling:
            return band, label, recommendation
    band, label, recommendation = RISK_BANDS[-1][1:]
    return band, label, recommendation


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
