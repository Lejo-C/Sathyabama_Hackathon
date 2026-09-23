"""Level 3 check tests - verification of the opportunity itself.

These tests also pin down the Level 1 / Level 3.3 boundary: fee *wording* in the
posting body belongs to Level 1, while a payment *instrument* or an instruction
served by the application flow belongs here.
"""

from __future__ import annotations

from app.level3_opportunity import (
    careers_page_check,
    cross_platform_search,
    payment_flow_detector,
    selection_process_analyzer,
)
from app.level3_opportunity.orchestrator import run_level3
from tests.conftest import dead_page, html_page, make_results, offline_fetch, offline_search
from tests.test_level2 import by_id


# --------------------------------------------------------------------------
# 3.1 cross-platform
# --------------------------------------------------------------------------

def test_cross_platform_listing_found(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        cross_platform_search, "web_search",
        lambda q, **k: make_results(
            ("Junior Data Analyst - Nimbus Analytics Private Limited",
             "https://www.linkedin.com/jobs/view/1234",
             "Nimbus Analytics Private Limited is hiring a Junior Data Analyst, Rs 4,50,000 per annum"),
            ("Junior Data Analyst | Nimbus Analytics Private Limited",
             "https://www.naukri.com/job-listings-5678",
             "Nimbus Analytics Private Limited, Chennai, Rs 4,50,000 per annum, posted 3 days ago"),
        ),
    )
    evidence = cross_platform_search.check_cross_platform(legit_claims, context)
    presence = by_id(evidence, "l3_cross_platform_presence")
    assert presence.status == "pass"
    assert set(presence.raw_data["platforms"]) == {"LinkedIn", "Naukri"}
    assert len(context["cross_platform_results"]) == 2


def test_cross_platform_absent_is_warning_not_fail(monkeypatch, scam_claims, context):
    monkeypatch.setattr(cross_platform_search, "web_search", lambda q, **k: [])
    presence = by_id(
        cross_platform_search.check_cross_platform(scam_claims, context),
        "l3_cross_platform_presence",
    )
    assert presence.status == "warning"


def test_cross_platform_salary_mismatch_fails(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        cross_platform_search, "web_search",
        lambda q, **k: make_results(
            ("Junior Data Analyst - Nimbus Analytics Private Limited",
             "https://www.naukri.com/job-listings-5678",
             "Nimbus Analytics Private Limited hiring Junior Data Analyst, Rs 25,000 per month"),
        ),
    )
    claims = legit_claims.model_copy(update={"salary": "Rs 12,00,000 per annum"})
    consistency = by_id(
        cross_platform_search.check_cross_platform(claims, context),
        "l3_cross_platform_consistency",
    )
    assert consistency.status == "fail"
    assert consistency.raw_data["mismatches"][0]["field"] == "salary"


def test_cross_platform_offline_is_unavailable(monkeypatch, legit_claims, context):
    monkeypatch.setattr(cross_platform_search, "web_search", offline_search)
    evidence = cross_platform_search.check_cross_platform(legit_claims, context)
    assert {e.status for e in evidence} == {"unavailable"}
    assert context["cross_platform_available"] is False


# --------------------------------------------------------------------------
# 3.2 careers page
# --------------------------------------------------------------------------

def test_careers_page_lists_the_role(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        careers_page_check, "fetch",
        lambda url, *a, **k: html_page(
            "Careers at Nimbus. Current openings: Junior Data Analyst, Chennai. Apply now.",
            url=url,
        ),
    )
    context["verified_domain"] = "nimbusanalytics.in"
    item = careers_page_check.check_careers_page(legit_claims, context)[0]
    assert item.status == "pass"


def test_careers_page_exists_but_role_missing_is_warning(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        careers_page_check, "fetch",
        lambda url, *a, **k: html_page(
            "Careers at Nimbus. Current openings: Senior Backend Engineer. We are hiring.",
            url=url,
        ),
    )
    context["verified_domain"] = "nimbusanalytics.in"
    item = careers_page_check.check_careers_page(legit_claims, context)[0]
    assert item.status == "warning"


def test_no_careers_page_is_unavailable_not_warning(monkeypatch, legit_claims, context):
    monkeypatch.setattr(careers_page_check, "fetch", lambda url, *a, **k: dead_page(url))
    context["verified_domain"] = "nimbusanalytics.in"
    item = careers_page_check.check_careers_page(legit_claims, context)[0]
    assert item.status == "unavailable"


def test_careers_page_without_verified_website(legit_claims, context):
    claims = legit_claims.model_copy(update={"website_url": None})
    item = careers_page_check.check_careers_page(claims, context)[0]
    assert item.status == "unavailable"


# --------------------------------------------------------------------------
# 3.3 payment in the application flow
# --------------------------------------------------------------------------

def test_upi_instrument_in_flow_fails_and_raises_the_hard_floor_flag(
    monkeypatch, scam_claims, context
):
    monkeypatch.setattr(payment_flow_detector, "fetch", lambda url, *a, **k: dead_page(url))
    evidence = payment_flow_detector.check_payment_flow(scam_claims, context)
    instrument = by_id(evidence, "l3_payment_instrument")
    assert instrument.status == "fail"
    assert context["payment_to_individual"] is True
    kinds = {entry["type"] for entry in instrument.raw_data["instruments"]}
    assert "upi_vpa" in kinds and "qr_request" in kinds


def test_payment_language_alone_is_left_to_level_1(monkeypatch, legit_claims, context):
    """Fee *wording* in the posting body must not be scored by Level 3.3."""
    claims = legit_claims.model_copy(
        update={
            "posting_text": "Selected candidates must pay a refundable registration "
            "fee of Rs 1,500 before onboarding.",
            "application_url": None,
        }
    )
    evidence = payment_flow_detector.check_payment_flow(claims, context)
    assert by_id(evidence, "l3_payment_instrument").status == "pass"
    assert context["payment_to_individual"] is False
    assert by_id(evidence, "l3_payment_flow_instruction").status == "unavailable"


def test_payment_instruction_on_application_page_fails(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        payment_flow_detector, "fetch",
        lambda url, *a, **k: html_page(
            "Step 3: pay the registration fee of Rs 999 and upload your payment screenshot.",
            url=url,
        ),
    )
    entry = by_id(
        payment_flow_detector.check_payment_flow(legit_claims, context),
        "l3_payment_flow_instruction",
    )
    assert entry.status == "fail"
    assert "registration fee" in entry.raw_data["matches"]


def test_gateway_collect_link_outside_company_domain_fails(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        payment_flow_detector, "fetch",
        lambda url, *a, **k: html_page(
            'Complete onboarding: <a href="https://rzp.io/l/hr-onboarding-fee">pay here</a>',
            url=url,
        ),
    )
    entry = by_id(
        payment_flow_detector.check_payment_flow(legit_claims, context),
        "l3_payment_gateway_link",
    )
    assert entry.status == "fail"
    assert entry.raw_data["gateway_links"][0]["provider"] == "Razorpay"


def test_clean_application_flow_passes(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        payment_flow_detector, "fetch",
        lambda url, *a, **k: html_page(
            "Apply for Junior Data Analyst. Upload your CV and answer three questions.",
            url=url,
        ),
    )
    evidence = payment_flow_detector.check_payment_flow(legit_claims, context)
    assert by_id(evidence, "l3_payment_instrument").status == "pass"
    assert by_id(evidence, "l3_payment_gateway_link").status == "pass"
    assert by_id(evidence, "l3_payment_flow_instruction").status == "pass"
    assert context["payment_to_individual"] is False


def test_recruiter_email_is_not_mistaken_for_a_upi_handle(legit_claims, context):
    claims = legit_claims.model_copy(
        update={"posting_text": "Write to careers@nimbusanalytics.in", "application_url": None}
    )
    entry = by_id(
        payment_flow_detector.check_payment_flow(claims, context), "l3_payment_instrument"
    )
    assert entry.status == "pass"


# --------------------------------------------------------------------------
# 3.4 selection process
# --------------------------------------------------------------------------

def test_selection_process_emits_one_item_per_matched_phrase(scam_claims, context):
    evidence = selection_process_analyzer.check_selection_process(scam_claims, context)
    ids = {entry.check_id for entry in evidence}
    assert {"l3_process_no_interview", "l3_process_instant_selection",
            "l3_process_whatsapp_only", "l3_process_join_immediately"} <= ids
    assert all(entry.status == "fail" for entry in evidence)
    assert all(entry.raw_data["matched_phrase"] for entry in evidence)


def test_selection_process_clean_posting_passes(legit_claims, context):
    evidence = selection_process_analyzer.check_selection_process(legit_claims, context)
    assert len(evidence) == 1
    assert evidence[0].status == "pass"


# --------------------------------------------------------------------------
# level report
# --------------------------------------------------------------------------

def test_level3_scores_scam_below_legit(monkeypatch, legit_claims, scam_claims):
    monkeypatch.setattr(cross_platform_search, "web_search", lambda q, **k: [])
    monkeypatch.setattr(careers_page_check, "fetch", lambda url, *a, **k: dead_page(url))
    monkeypatch.setattr(payment_flow_detector, "fetch", lambda url, *a, **k: dead_page(url))

    legit_report = run_level3(legit_claims, {})
    scam_report = run_level3(scam_claims, {})
    assert scam_report.level_score < legit_report.level_score
    assert scam_report.checks_failed >= 4


def test_level3_survives_total_network_outage(monkeypatch, scam_claims):
    monkeypatch.setattr(cross_platform_search, "web_search", offline_search)
    monkeypatch.setattr(careers_page_check, "fetch", offline_fetch)
    monkeypatch.setattr(payment_flow_detector, "fetch", offline_fetch)

    report = run_level3(scam_claims, {})
    assert report.evidence
    # The offline rule-based signals still fire: payment instrument + process flags.
    assert report.checks_failed >= 2
    assert 0 <= report.level_score <= 100
