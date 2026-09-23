"""One number, and the full account of where it came from.

Level 1 (poster/text analysis, owned by a teammate) and Levels 2-4 (external
verification, this module) each produce a 0-100 safety score. This file merges
them into the single candidate-facing **risk score**, 0-100 with higher =
riskier, and publishes the breakdown behind it:

* ``contributors``     - every check that cost points, with its priority, the
  points it removed and its share of the total risk raised;
* ``level_breakdown``  - each level's weight, score and share of the verdict;
* ``LevelReport.basis``- one line per level stating how its score was reached.

Weighting is 40% Level 1 / 60% Levels 2-4: a scammer writes their own advert,
but they do not control WHOIS, DNS, job boards or public complaints. With no
Level 1 report supplied, its share is redistributed across Levels 2-4 and the
response says so rather than pretending the text passed.

Hard floors still override everything at the end.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .core.schemas import (
    Contributor,
    EvidenceItem,
    ExtractedClaims,
    FinalVerdict,
    Level1Flag,
    Level1Report,
    LevelReport,
    Priority,
)
from .core.scoring import (
    LEVEL1_WEIGHT,
    LEVEL_WEIGHTS,
    LEVELS_2_4_WEIGHT,
    PRIORITY_POINTS,
    apply_hard_floors,
    band_for,
    build_contributors,
    combine_final,
    describe_basis,
    final_level_shares,
    is_low_confidence,
    penalty_for,
    score_evidence,
)
from .level2_4_orchestrator import collect_hard_floor_flags, run_levels_2_to_4
from .shared.explainer import explain

logger = logging.getLogger(__name__)

SEVERITY_ALIASES: dict[str, Priority] = {
    "critical": "critical", "severe": "critical", "blocker": "critical",
    "high": "high", "major": "high",
    "medium": "medium", "moderate": "medium", "warning": "medium",
    "low": "low", "minor": "low", "info": "low",
}


def normalise_severity(severity: str | None) -> Priority:
    """Map whatever Level 1 calls a severity onto our four tiers."""
    return SEVERITY_ALIASES.get((severity or "").strip().lower(), "medium")


def level1_to_report(level1: Level1Report) -> LevelReport:
    """Turn the Level 1 hand-off into a LevelReport scored like every other level.

    If Level 1 supplied a score we honour it; otherwise it is derived from the
    flags by priority, using exactly the same points table as Levels 2-4.
    """
    evidence = [_flag_to_evidence(flag) for flag in level1.flags if flag.flagged]

    if level1.level_score is not None:
        score = float(level1.level_score)
    elif level1.risk_score is not None:
        score = 100.0 - float(level1.risk_score)
    else:
        score = score_evidence(evidence)

    score = max(0.0, min(100.0, score))
    for item in evidence:
        item.points = round(penalty_for(item), 2)

    basis = describe_basis(evidence, score) if evidence else (
        f"Level 1 reported a score of {score:g}/100 with no itemised flags."
    )
    if level1.level_score is None and level1.risk_score is None and not evidence:
        basis = "Level 1 supplied neither a score nor any flags."

    return LevelReport.from_evidence(
        1, evidence, score,
        contributors=build_contributors(evidence),
        basis=basis,
    )


def _flag_to_evidence(flag: Level1Flag) -> EvidenceItem:
    priority = normalise_severity(str(flag.severity))
    return EvidenceItem(
        level=1,
        check_id=flag.id if flag.id.startswith("l1_") else f"l1_{flag.id}",
        label=flag.title,
        status="fail",
        finding=flag.explanation or flag.evidence or flag.title,
        raw_data={
            "evidence": flag.evidence,
            "category": flag.category,
            "reported_severity": str(flag.severity),
        },
        risk_weight=PRIORITY_POINTS[priority],
        confidence=1.0,
        priority=priority,
    )


def build_final_verdict(
    claims: ExtractedClaims,
    level1: Level1Report | None = None,
    context: dict[str, Any] | None = None,
) -> FinalVerdict:
    """Run Levels 2-4, merge Level 1 if present, and return the whole verdict."""
    started = time.perf_counter()
    context = context if context is not None else {}

    level2, level3, level4 = run_levels_2_to_4(claims, context)
    level1_report = level1_to_report(level1) if level1 is not None else None
    include_level1 = level1_report is not None

    level_scores = {
        2: level2.level_score, 3: level3.level_score, 4: level4.level_score
    }
    if level1_report is not None:
        level_scores[1] = level1_report.level_score

    safety = combine_final(level_scores, include_level1)
    flags = collect_hard_floor_flags(context)
    safety, applied = apply_hard_floors(safety, flags)
    risk = round(100.0 - safety, 2)
    band, band_label, recommendation = band_for(risk)

    reports = [r for r in (level1_report, level2, level3, level4) if r is not None]
    evidence_2_to_4 = [*level2.evidence, *level3.evidence, *level4.evidence]
    low_confidence = is_low_confidence(evidence_2_to_4)

    contributors = _merged_contributors(reports, include_level1)
    breakdown = _level_breakdown(reports, contributors, include_level1)

    summary, source = explain(
        [*(level1_report.evidence if level1_report else []), *evidence_2_to_4],
        safety,
        claims.company_name,
    )
    summary = _augment_summary(
        summary, risk, band_label, applied, low_confidence, include_level1, contributors
    )

    return FinalVerdict(
        risk_score=risk,
        safety_score=round(safety, 2),
        band=band,
        band_label=band_label,
        recommendation=recommendation,
        level1=level1_report,
        level2=level2,
        level3=level3,
        level4=level4,
        contributors=contributors,
        level_breakdown=breakdown,
        weights_used=_weights_used(include_level1),
        hard_floors_applied=applied,
        low_confidence=low_confidence,
        level1_included=include_level1,
        summary=summary,
        explainer_source=source,
        processing_time_ms=int((time.perf_counter() - started) * 1000),
    )


def _merged_contributors(
    reports: list[LevelReport], include_level1: bool
) -> list[Contributor]:
    """Every point-costing check across all levels, weighted by level share."""
    shares = final_level_shares(include_level1)
    weighted: list[tuple[EvidenceItem, float]] = []
    for report in reports:
        share = shares.get(report.level, 0.0)
        for item in report.evidence:
            points = penalty_for(item) * share
            if points > 0:
                weighted.append((item, points))

    total = sum(points for _, points in weighted)
    contributors = [
        Contributor(
            check_id=item.check_id,
            title=item.label,
            level=item.level,
            priority=item.priority,
            status=item.status,
            points=round(points, 2),
            percentage=round(100.0 * points / total, 1) if total else 0.0,
            finding=item.finding,
        )
        for item, points in weighted
    ]
    contributors.sort(key=lambda c: c.points, reverse=True)
    return contributors


def _level_breakdown(
    reports: list[LevelReport], contributors: list[Contributor], include_level1: bool
) -> list[dict[str, Any]]:
    shares = final_level_shares(include_level1)
    names = {
        1: "Poster & text analysis",
        2: "Company background",
        3: "The opportunity",
        4: "External evidence",
    }
    return [
        {
            "level": report.level,
            "name": names.get(report.level, f"Level {report.level}"),
            "weight": round(shares.get(report.level, 0.0), 3),
            "safety_score": report.level_score,
            "risk_score": report.risk_score,
            "risk_share_pct": round(
                sum(c.percentage for c in contributors if c.level == report.level), 1
            ),
            "checks_run": report.checks_run,
            "checks_failed": report.checks_failed,
            "checks_warning": report.checks_warning,
            "checks_unavailable": report.checks_unavailable,
            "basis": report.basis,
        }
        for report in reports
    ]


def _weights_used(include_level1: bool) -> dict[str, float]:
    shares = final_level_shares(include_level1)
    used = {f"level{level}": round(share, 3) for level, share in sorted(shares.items())}
    used["level1_block"] = LEVEL1_WEIGHT if include_level1 else 0.0
    used["levels_2_4_block"] = LEVELS_2_4_WEIGHT if include_level1 else 1.0
    used.update({f"within_2_4_level{k}": v for k, v in LEVEL_WEIGHTS.items()})
    return used


def _augment_summary(
    summary: str,
    risk: float,
    band_label: str,
    applied: list[str],
    low_confidence: bool,
    include_level1: bool,
    contributors: list[Contributor],
) -> str:
    parts = [f"Final verdict: {risk:g}/100 risk - {band_label}.", summary]
    if contributors:
        top = contributors[0]
        parts.append(
            f"The single largest driver is {top.title} (Level {top.level}, "
            f"{top.priority} priority, {top.percentage:g}% of the risk raised)."
        )
    if not include_level1:
        parts.append(
            "No Level 1 poster analysis was supplied, so this verdict rests on "
            "external verification alone."
        )
    if low_confidence:
        parts.append(
            "Most external lookups were unreachable, so treat this as provisional."
        )
    return " ".join(part for part in parts if part)
