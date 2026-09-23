"""Priority scoring, the risk breakdown, and the Level 1 + Levels 2-4 merge."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.schemas import (
    EvidenceItem,
    FinalVerdictRequest,
    Level1Flag,
    Level1Report,
)
from app.core.scoring import (
    CHECK_PRIORITY,
    HARD_FLOORS,
    LEVEL1_WEIGHT,
    PRIORITY_POINTS,
    band_for,
    build_level_report,
    combine_final,
    final_level_shares,
    priority_for,
    weight,
)
from app.final_verdict import build_final_verdict, level1_to_report, normalise_severity
from app.main import app


def item(check_id: str, status: str, level: int = 2) -> EvidenceItem:
    return EvidenceItem(
        level=level, check_id=check_id, label=check_id.replace("_", " ").title(),
        status=status, finding="f", risk_weight=weight(check_id),
        priority=priority_for(check_id),
    )


# --------------------------------------------------------------------------
# priority drives the weight
# --------------------------------------------------------------------------

def test_every_check_declares_a_priority():
    assert set(CHECK_PRIORITY) >= {
        "l2_location", "l2_company_existence", "l2_domain_age", "l2_website_live",
        "l2_domain_name_match", "l2_contact_intl_prefix", "l2_contact_public_match",
        "l2_email_domain_match", "l2_email_free_provider", "l2_email_mx",
        "l3_cross_platform_presence", "l3_cross_platform_consistency",
        "l3_careers_page", "l3_payment_instrument", "l3_payment_gateway_link",
        "l3_payment_flow_instruction", "l3_selection_process",
        "l4_fraud_mentions", "l4_review_presence", "l4_repost_pattern",
        "l4_listing_age",
    }


def test_weight_follows_the_priority_tier():
    assert weight("l4_review_presence") == PRIORITY_POINTS["low"]
    assert weight("l2_domain_age") == PRIORITY_POINTS["high"]
    assert weight("l2_contact_intl_prefix") == PRIORITY_POINTS["critical"]


def test_payment_instrument_is_charged_above_its_tier():
    """A confirmed payee handle should sink its level on its own."""
    assert weight("l3_payment_instrument") > PRIORITY_POINTS["critical"]


def test_a_critical_failure_outweighs_a_low_one():
    critical = build_level_report(2, [item("l2_contact_intl_prefix", "fail")])
    low = build_level_report(2, [item("l2_review_presence", "fail")])
    assert critical.level_score < low.level_score


# --------------------------------------------------------------------------
# the breakdown: on what basis was this level scored
# --------------------------------------------------------------------------

def test_level_report_publishes_contributors_sorted_by_points():
    report = build_level_report(2, [
        item("l2_contact_public_match", "fail"),
        item("l2_contact_intl_prefix", "fail"),
        item("l2_company_existence", "warning"),
        item("l2_email_mx", "pass"),
    ])
    assert [c.check_id for c in report.contributors][0] == "l2_contact_intl_prefix"
    assert all(c.status != "pass" for c in report.contributors)
    assert abs(sum(c.percentage for c in report.contributors) - 100.0) < 0.5


def test_level_report_basis_states_how_the_score_was_reached():
    report = build_level_report(2, [
        item("l2_contact_intl_prefix", "fail"), item("l2_email_mx", "pass")
    ])
    assert "2 checks" in report.basis
    assert "1 failed" in report.basis
    assert "Contact Intl Prefix" in report.basis or "l2_contact_intl_prefix" in report.basis
    assert report.risk_score == round(100.0 - report.level_score, 2)


def test_evidence_items_carry_the_points_they_cost():
    report = build_level_report(2, [item("l2_domain_age", "fail")])
    scored = report.evidence[0]
    assert scored.points == PRIORITY_POINTS["high"]
    assert scored.priority == "high"


def test_unavailable_checks_contribute_nothing_to_the_breakdown():
    report = build_level_report(2, [item("l2_domain_age", "unavailable")])
    assert report.contributors == []
    assert report.level_score == 100.0


# --------------------------------------------------------------------------
# Level 1 hand-off
# --------------------------------------------------------------------------

def test_level1_score_derived_from_flags_when_none_supplied():
    report = level1_to_report(Level1Report(flags=[
        Level1Flag(id="upfront_payment", title="Upfront Payment", severity="CRITICAL"),
        Level1Flag(id="urgency", title="Urgency Language", severity="HIGH"),
    ]))
    expected = 100.0 - PRIORITY_POINTS["critical"] - PRIORITY_POINTS["high"]
    assert report.level_score == pytest.approx(expected)
    assert report.level == 1
    assert [c.priority for c in report.contributors] == ["critical", "high"]


def test_level1_risk_score_is_honoured_when_supplied():
    report = level1_to_report(Level1Report(risk_score=74.0))
    assert report.level_score == 26.0
    assert report.risk_score == 74.0


def test_level1_safety_score_is_honoured_when_supplied():
    assert level1_to_report(Level1Report(level_score=31.0)).level_score == 31.0


@pytest.mark.parametrize("given,expected", [
    ("CRITICAL", "critical"), ("High", "high"), ("moderate", "medium"),
    ("minor", "low"), ("", "medium"), ("nonsense", "medium"),
])
def test_severity_aliases_are_normalised(given, expected):
    assert normalise_severity(given) == expected


def test_dashboard_payload_is_accepted_as_level1():
    """The shape already in mockJobData.js must merge without a rewrite."""
    request = FinalVerdictRequest(
        claims={"posting_text": "text"},
        level1={
            "score": 74,
            "summary": {"keyThreat": "Mandatory upfront registration fee."},
            "riskFactors": [
                {"id": "upfront_payment", "title": "Upfront Payment",
                 "severity": "CRITICAL", "evidence": "pay Rs 1,500",
                 "explanation": "Employers never charge candidates.",
                 "category": "Financial Fraud", "flagged": True},
                {"id": "urgency_language", "title": "Urgency Language",
                 "severity": "HIGH", "evidence": "closes in 2 hours"},
            ],
        },
    )
    assert request.level1 is not None
    assert request.level1.risk_score == 74.0
    assert [flag.id for flag in request.level1.flags] == [
        "upfront_payment", "urgency_language"
    ]
    assert request.level1.summary.startswith("Mandatory upfront")


# --------------------------------------------------------------------------
# weighting
# --------------------------------------------------------------------------

def test_level_shares_sum_to_one_with_and_without_level1():
    with_l1 = final_level_shares(True)
    assert with_l1[1] == LEVEL1_WEIGHT
    assert sum(with_l1.values()) == pytest.approx(1.0)
    without = final_level_shares(False)
    assert 1 not in without
    assert sum(without.values()) == pytest.approx(1.0)


def test_level1_carries_forty_percent_of_the_verdict():
    safety = combine_final({1: 0.0, 2: 100.0, 3: 100.0, 4: 100.0}, include_level1=True)
    assert safety == pytest.approx(60.0)


def test_missing_level1_redistributes_its_weight():
    safety = combine_final({2: 50.0, 3: 50.0, 4: 50.0}, include_level1=False)
    assert safety == pytest.approx(50.0)


@pytest.mark.parametrize("risk,band", [
    (0.0, "LOW"), (24.9, "LOW"), (25.0, "MEDIUM"), (49.9, "MEDIUM"),
    (50.0, "HIGH"), (74.9, "HIGH"), (75.0, "CRITICAL"), (100.0, "CRITICAL"),
])
def test_risk_bands(risk, band):
    assert band_for(risk)[0] == band


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------

def test_final_verdict_merges_level1_with_levels_2_to_4(offline, legit_claims):
    """Offline, Levels 2-4 find nothing, so Level 1 supplies exactly 40%."""
    verdict = build_final_verdict(legit_claims, Level1Report(risk_score=80.0))
    assert verdict.level1_included is True
    assert verdict.risk_score == pytest.approx(32.0, abs=0.5)
    assert verdict.safety_score == pytest.approx(100.0 - verdict.risk_score, abs=0.01)
    assert verdict.band == "MEDIUM"
    assert verdict.band_label == "MEDIUM RISK"
    assert verdict.recommendation


def test_final_verdict_without_level1_is_marked(offline, legit_claims):
    verdict = build_final_verdict(legit_claims)
    assert verdict.level1_included is False
    assert verdict.level1 is None
    assert "No Level 1" in verdict.summary
    assert verdict.weights_used["level1_block"] == 0.0


def test_final_verdict_shows_what_drove_the_risk(offline, scam_claims):
    verdict = build_final_verdict(scam_claims, Level1Report(flags=[
        Level1Flag(id="upfront_payment", title="Upfront Payment", severity="critical"),
    ]))
    assert verdict.contributors
    assert abs(sum(c.percentage for c in verdict.contributors) - 100.0) < 1.0
    top = verdict.contributors[0]
    assert top.points > 0 and top.finding and top.priority in PRIORITY_POINTS
    assert verdict.contributors == sorted(
        verdict.contributors, key=lambda c: c.points, reverse=True
    )
    # Every level that ran is accounted for, with its own basis line.
    levels = {row["level"] for row in verdict.level_breakdown}
    assert levels == {1, 2, 3, 4}
    assert all(row["basis"] for row in verdict.level_breakdown)
    assert sum(row["risk_share_pct"] for row in verdict.level_breakdown) == pytest.approx(
        100.0, abs=1.5
    )


def test_hard_floor_still_overrides_the_merged_score(offline, scam_claims):
    verdict = build_final_verdict(scam_claims, Level1Report(risk_score=0.0))
    assert "payment_to_individual" in verdict.hard_floors_applied
    assert verdict.risk_score >= 100.0 - HARD_FLOORS["payment_to_individual"]
    assert verdict.band == "CRITICAL"


def test_level2_risk_is_visible_on_its_own_terms(offline, scam_claims):
    verdict = build_final_verdict(scam_claims)
    level2 = verdict.level2
    assert level2.basis
    assert level2.risk_score > 0
    assert level2.contributors
    assert all(c.level == 2 for c in level2.contributors)
    row = next(r for r in verdict.level_breakdown if r["level"] == 2)
    assert row["name"] == "Company background"
    assert row["weight"] > 0


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

def test_final_endpoint_returns_one_risk_number(offline, scam_claims):
    with TestClient(app) as client:
        response = client.post("/api/verify/final", json={
            "claims": scam_claims.model_dump(),
            "level1": {"score": 74, "riskFactors": [
                {"id": "upfront_payment", "title": "Upfront Payment",
                 "severity": "CRITICAL", "evidence": "Rs 1,500 fee"},
            ]},
        })
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["risk_score"] <= 100
    assert body["band"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert body["level1_included"] is True
    assert body["level1"]["level"] == 1
    assert body["contributors"] and body["level_breakdown"]
    assert body["level2"]["basis"]


def test_final_endpoint_works_without_level1(offline, legit_claims):
    with TestClient(app) as client:
        response = client.post(
            "/api/verify/final", json={"claims": legit_claims.model_dump()}
        )
    assert response.status_code == 200
    assert response.json()["level1_included"] is False
