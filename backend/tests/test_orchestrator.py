"""End-to-end tests for the Level 2-4 orchestrator, hard floors and API.

The point of these tests is the two promises the product makes on stage:

1. a confirmed payment demand (or the other floor conditions) caps the score no
   matter how well everything else scores;
2. with every external lookup dead, the endpoint still returns a valid,
   honestly-labelled response instead of an error.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.schemas import EvidenceItem
from app.core.scoring import HARD_FLOORS, apply_hard_floors, score_evidence
from app.level2_4_orchestrator import collect_hard_floor_flags, verify_company_opportunity
from app.main import app
from app.shared.explainer import build_template_summary, explain
from tests.conftest import html_page


def evidence_item(status: str, weight: float = 20.0, confidence: float = 1.0) -> EvidenceItem:
    return EvidenceItem(
        level=2, check_id="x", label="X", status=status, finding="f",
        risk_weight=weight, confidence=confidence,
    )


# --------------------------------------------------------------------------
# scoring primitives
# --------------------------------------------------------------------------

def test_unavailable_checks_cost_nothing():
    assert score_evidence([evidence_item("unavailable"), evidence_item("pass")]) == 100.0


def test_warning_costs_less_than_fail():
    warning = score_evidence([evidence_item("warning")])
    failure = score_evidence([evidence_item("fail")])
    assert 100.0 > warning > failure


def test_low_confidence_softens_the_penalty():
    confident = score_evidence([evidence_item("fail", confidence=1.0)])
    unsure = score_evidence([evidence_item("fail", confidence=0.5)])
    assert unsure > confident


@pytest.mark.parametrize("flag,ceiling", sorted(HARD_FLOORS.items()))
def test_each_hard_floor_caps_a_perfect_score(flag, ceiling):
    score, applied = apply_hard_floors(100.0, {flag: True})
    assert score == ceiling
    assert applied == [flag]


def test_hard_floor_never_raises_a_lower_score():
    score, applied = apply_hard_floors(4.0, {"payment_to_individual": True})
    assert score == 4.0
    assert applied == ["payment_to_individual"]


def test_no_flags_leave_the_score_alone():
    score, applied = apply_hard_floors(88.0, {})
    assert (score, applied) == (88.0, [])


def test_flag_collection_from_context():
    flags = collect_hard_floor_flags(
        {"payment_to_individual": True, "domain_age_days": 12,
         "email_domain_mismatch": True, "intl_contact_flag": True,
         "company_verified": False}
    )
    assert all(flags.values())


def test_new_domain_floor_needs_both_conditions():
    assert not collect_hard_floor_flags(
        {"domain_age_days": 12, "email_domain_mismatch": False}
    )["new_domain_and_email_mismatch"]
    assert not collect_hard_floor_flags(
        {"domain_age_days": 400, "email_domain_mismatch": True}
    )["new_domain_and_email_mismatch"]


def test_intl_floor_clears_when_company_is_verified():
    assert not collect_hard_floor_flags(
        {"intl_contact_flag": True, "company_verified": True}
    )["intl_contact_unverified_company"]


# --------------------------------------------------------------------------
# hard floors through the whole pipeline
# --------------------------------------------------------------------------

def test_payment_instrument_caps_the_combined_score(offline, scam_claims):
    response = verify_company_opportunity(scam_claims)
    assert "payment_to_individual" in response.hard_floors_applied
    assert response.combined_score <= HARD_FLOORS["payment_to_individual"]
    assert response.combined_risk_score >= 100 - HARD_FLOORS["payment_to_individual"]


def test_new_domain_plus_email_mismatch_caps_the_score(monkeypatch, legit_claims):
    claims = legit_claims.model_copy(
        update={"recruiter_email": "nimbus.hr.team@gmail.com", "application_url": None}
    )
    monkeypatch.setattr(
        "app.level2_company.website_check.domain_age",
        lambda domain, **kwargs: __import__(
            "app.shared.domain_utils", fromlist=["DomainAge"]
        ).DomainAge(domain=domain, created_at=None, age_days=11,
                    registrar="R", country="IN"),
    )
    for name in ("app.level2_company.website_check", "app.level2_company.location_check",
                 "app.level3_opportunity.careers_page_check",
                 "app.level3_opportunity.payment_flow_detector"):
        monkeypatch.setattr(name + ".fetch",
                            lambda url, *a, **k: html_page("Nimbus Analytics " + "x" * 400, url=url))
    for name in ("app.level2_company.location_check", "app.level2_company.existence_check",
                 "app.level2_company.contact_check",
                 "app.level3_opportunity.cross_platform_search",
                 "app.level4_evidence.review_scraper"):
        monkeypatch.setattr(name + ".web_search", lambda q, **k: [])
    monkeypatch.setattr("app.level2_company.hr_email_check.has_mx", lambda host, **k: True)

    response = verify_company_opportunity(claims)
    assert "new_domain_and_email_mismatch" in response.hard_floors_applied
    assert response.combined_score <= HARD_FLOORS["new_domain_and_email_mismatch"]


def test_international_contact_without_verified_company_caps_the_score(offline, legit_claims):
    claims = legit_claims.model_copy(
        update={"recruiter_phone": "+60 12-345 6789", "application_url": None,
                "posting_text": "Work from home role for candidates across India. "
                                "Contact our recruiter on +60 12-345 6789."}
    )
    response = verify_company_opportunity(claims)
    assert "intl_contact_unverified_company" in response.hard_floors_applied
    assert response.combined_score <= HARD_FLOORS["intl_contact_unverified_company"]


# --------------------------------------------------------------------------
# graceful degradation
# --------------------------------------------------------------------------

def test_fully_offline_run_still_returns_a_valid_response(offline, legit_claims):
    response = verify_company_opportunity(legit_claims)
    assert 0.0 <= response.combined_score <= 100.0
    assert response.low_confidence is True
    assert response.combined_summary
    assert response.explainer_source == "template"
    assert response.processing_time_ms >= 0
    for report in (response.level2, response.level3, response.level4):
        assert report.checks_run == len(report.evidence) > 0
    assert "provisional" in response.combined_summary


def test_offline_run_does_not_invent_failures(offline, legit_claims):
    response = verify_company_opportunity(legit_claims)
    network_dependent = [
        entry for entry in response.level2.evidence
        if entry.check_id in {"l2_location", "l2_company_existence", "l2_domain_age"}
    ]
    assert all(entry.status == "unavailable" for entry in network_dependent)


def test_explainer_falls_back_to_template_without_a_key(offline):
    evidence = [evidence_item("fail"), evidence_item("unavailable")]
    summary, source = explain(evidence, 22.0, "Apex Global Innovators Inc.")
    assert source == "template"
    assert summary == build_template_summary(evidence, 22.0)
    assert "22/100" in summary


def test_template_summary_mentions_unavailable_checks():
    summary = build_template_summary([evidence_item("unavailable")], 100.0)
    assert "not proof of legitimacy" in summary


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------

def test_endpoint_returns_all_three_levels(offline, scam_claims):
    with TestClient(app) as client:
        response = client.post(
            "/api/verify/company-opportunity", json=scam_claims.model_dump()
        )
    assert response.status_code == 200
    body = response.json()
    assert {body["level2"]["level"], body["level3"]["level"], body["level4"]["level"]} == {2, 3, 4}
    assert body["combined_score"] <= HARD_FLOORS["payment_to_individual"]
    assert body["combined_summary"]
    assert "payment_to_individual" in body["hard_floors_applied"]
    assert body["explainer_source"] == "template"
    # Offline, but the scam posting still trips enough offline rule-based checks
    # that the verdict does not rest on unavailable lookups.
    assert body["low_confidence"] is False
    assert body["level3"]["checks_failed"] >= 4


def test_endpoint_rejects_a_payload_without_posting_text():
    with TestClient(app) as client:
        response = client.post("/api/verify/company-opportunity", json={"company_name": "X"})
    assert response.status_code == 422


def test_health_endpoint_reports_degraded_offline(offline, monkeypatch):
    monkeypatch.setattr("app.api.verification.fetch",
                        lambda url, **kwargs: html_page("", status=503, url=url))
    monkeypatch.setattr("app.api.verification.web_search",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr("app.api.verification.domain_age",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr("app.api.verification.has_mx",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    with TestClient(app) as client:
        response = client.get("/api/verify/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert {dep["name"] for dep in body["dependencies"]} == {
        "http", "web_search", "whois", "dns", "groq"
    }
    assert all(dep["available"] is False for dep in body["dependencies"])
