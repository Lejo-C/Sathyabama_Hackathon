"""Level 2 check tests - company background verification.

Every external call is patched, so the suite is deterministic and works offline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.schemas import EvidenceItem
from app.level2_company import (
    contact_check,
    existence_check,
    hr_email_check,
    location_check,
    website_check,
)
from app.level2_company.orchestrator import run_level2
from app.shared.domain_utils import DomainAge, WhoisUnavailable
from app.shared.email_utils import DnsUnavailable
from app.shared.web_search import SearchUnavailable
from tests.conftest import dead_page, html_page, make_results, offline_fetch, offline_search


def by_id(evidence: list[EvidenceItem], check_id: str) -> EvidenceItem:
    for entry in evidence:
        if entry.check_id == check_id:
            return entry
    raise AssertionError(f"{check_id} not in {[e.check_id for e in evidence]}")


def age(days: int, domain: str = "example.com") -> DomainAge:
    return DomainAge(
        domain=domain,
        created_at=datetime.now(timezone.utc) - timedelta(days=days),
        age_days=days,
        registrar="Test Registrar",
        country="IN",
    )


# --------------------------------------------------------------------------
# 2.1 location
# --------------------------------------------------------------------------

def test_location_confirmed_on_company_site(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        location_check, "fetch",
        lambda url, *a, **k: html_page(
            "Nimbus Analytics, Guindy, Chennai, Tamil Nadu 600032. " + "x" * 300
        ),
    )
    item = location_check.check_location(legit_claims, context)[0]
    assert item.status == "pass"
    assert "Chennai" in item.finding


def test_location_contradicted_by_company_site(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        location_check, "fetch",
        lambda url, *a, **k: html_page(
            "Our only office is in Hyderabad, Telangana. " + "x" * 300
        ),
    )
    item = location_check.check_location(legit_claims, context)[0]
    assert item.status == "fail"
    assert item.raw_data["site_location"] == "hyderabad"


def test_location_absent_evidence_is_only_a_warning(monkeypatch, legit_claims, context):
    monkeypatch.setattr(location_check, "fetch", lambda url, *a, **k: dead_page(url))
    monkeypatch.setattr(
        location_check, "web_search",
        lambda q, **k: make_results(
            ("Nimbus Analytics Private Limited", "https://example.com/n", "analytics firm")
        ),
    )
    item = location_check.check_location(legit_claims, context)[0]
    assert item.status == "warning", "absence of evidence must never be a fail"


def test_location_remote_only_claim_is_unverifiable(scam_claims, context):
    item = location_check.check_location(scam_claims, context)[0]
    assert item.status == "warning"
    assert item.raw_data["verifiable_tokens"] == []


def test_location_unavailable_when_search_is_offline(monkeypatch, legit_claims, context):
    monkeypatch.setattr(location_check, "fetch", offline_fetch)
    monkeypatch.setattr(location_check, "web_search", offline_search)
    item = location_check.check_location(legit_claims, context)[0]
    assert item.status == "unavailable"
    assert item.confidence == 0.0


# --------------------------------------------------------------------------
# 2.2 company existence
# --------------------------------------------------------------------------

def test_existence_pass_on_credible_source(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        existence_check, "web_search",
        lambda q, **k: make_results(
            ("Nimbus Analytics Private Limited - Company Profile",
             "https://www.zaubacorp.com/company/nimbus-analytics",
             "Nimbus Analytics Private Limited is registered under CIN U72900TN..."),
        ),
    )
    item = existence_check.check_existence(legit_claims, context)[0]
    assert item.status == "pass"
    assert context["company_verified"] is True


def test_existence_fail_when_no_trace_at_all(monkeypatch, scam_claims, context):
    monkeypatch.setattr(existence_check, "web_search", lambda q, **k: [])
    item = existence_check.check_existence(scam_claims, context)[0]
    assert item.status == "fail"
    assert context["company_verified"] is False


def test_existence_warning_on_thin_footprint(monkeypatch, scam_claims, context):
    monkeypatch.setattr(
        existence_check, "web_search",
        lambda q, **k: make_results(
            ("Apex Global Innovators Inc. hiring now",
             "https://random-blogspot.example/post",
             "Apex Global Innovators Inc. is hiring data entry staff"),
        ),
    )
    item = existence_check.check_existence(scam_claims, context)[0]
    assert item.status == "warning"
    assert context["company_verified"] is False


def test_existence_unknown_when_search_offline(monkeypatch, scam_claims, context):
    monkeypatch.setattr(existence_check, "web_search", offline_search)
    item = existence_check.check_existence(scam_claims, context)[0]
    assert item.status == "unavailable"
    assert context["company_verified"] is None, "offline must not be read as 'fake'"


# --------------------------------------------------------------------------
# 2.3 website
# --------------------------------------------------------------------------

def test_website_new_domain_fails_under_30_days(monkeypatch, scam_claims, context):
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(9, d))
    monkeypatch.setattr(
        website_check, "fetch",
        lambda url, *a, **k: html_page("Apex Global Innovators Inc. " + "content " * 80),
    )
    evidence = website_check.check_website(scam_claims, context)
    assert by_id(evidence, "l2_domain_age").status == "fail"
    assert context["domain_age_days"] == 9


def test_website_young_domain_is_only_a_warning(monkeypatch, scam_claims, context):
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(60, d))
    monkeypatch.setattr(
        website_check, "fetch",
        lambda url, *a, **k: html_page("Apex Global Innovators Inc. " + "content " * 80),
    )
    evidence = website_check.check_website(scam_claims, context)
    assert by_id(evidence, "l2_domain_age").status == "warning"


def test_website_parked_page_fails(monkeypatch, scam_claims, context):
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(400, d))
    monkeypatch.setattr(website_check, "fetch", lambda url, *a, **k: html_page("Coming soon"))
    evidence = website_check.check_website(scam_claims, context)
    live = by_id(evidence, "l2_website_live")
    assert live.status == "fail"
    assert "parked" in live.finding


def test_website_non_resolving_domain_fails(monkeypatch, scam_claims, context):
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(400, d))
    monkeypatch.setattr(
        website_check, "fetch",
        lambda url, *a, **k: dead_page(url, "ConnectionError: NameResolutionError"),
    )
    assert by_id(website_check.check_website(scam_claims, context), "l2_website_live").status == "fail"


def test_website_network_blip_is_unavailable_not_fail(monkeypatch, scam_claims, context):
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(400, d))
    monkeypatch.setattr(website_check, "fetch", offline_fetch)
    live = by_id(website_check.check_website(scam_claims, context), "l2_website_live")
    assert live.status == "unavailable"


def test_website_whois_failure_is_unavailable(monkeypatch, scam_claims, context):
    def boom(domain, **kwargs):
        raise WhoisUnavailable("whois timed out after 6s")

    monkeypatch.setattr(website_check, "domain_age", boom)
    monkeypatch.setattr(website_check, "fetch", lambda url, *a, **k: html_page("x" * 400))
    entry = by_id(website_check.check_website(scam_claims, context), "l2_domain_age")
    assert entry.status == "unavailable"
    assert entry.confidence == 0.0


def test_website_short_brand_name_on_page_is_enough(monkeypatch, legit_claims, context):
    """A site saying "Nimbus" must not be flagged for omitting "Private Limited"."""
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(900, d))
    monkeypatch.setattr(
        website_check, "fetch",
        lambda url, *a, **k: html_page("Welcome to Nimbus. Analytics for retail. " + "x" * 400),
    )
    entry = by_id(website_check.check_website(legit_claims, context), "l2_website_live")
    assert entry.status == "pass"


def test_website_unrelated_content_still_warns(monkeypatch, legit_claims, context):
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(900, d))
    monkeypatch.setattr(
        website_check, "fetch",
        lambda url, *a, **k: html_page("Cheap flight deals and hotel bookings. " + "x" * 400),
    )
    entry = by_id(website_check.check_website(legit_claims, context), "l2_website_live")
    assert entry.status == "warning"


def test_website_typosquat_domain_fails(monkeypatch, legit_claims, context):
    claims = legit_claims.model_copy(
        update={"company_name": "Amazon", "website_url": "https://arnazon-careers.com"}
    )
    monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(500, d))
    monkeypatch.setattr(website_check, "fetch", lambda url, *a, **k: html_page("Amazon " + "x" * 400))
    entry = by_id(website_check.check_website(claims, context), "l2_domain_name_match")
    assert entry.status == "fail"
    assert entry.raw_data["match_ratio"] < website_check.TYPOSQUAT_FAIL_RATIO


def test_website_checks_unavailable_without_a_website(legit_claims, context):
    claims = legit_claims.model_copy(update={"website_url": None})
    evidence = website_check.check_website(claims, context)
    assert {e.status for e in evidence} == {"unavailable"}
    assert len(evidence) == 3


# --------------------------------------------------------------------------
# 2.4 contact
# --------------------------------------------------------------------------

def test_contact_international_prefix_on_indian_role_fails(monkeypatch, scam_claims, context):
    monkeypatch.setattr(contact_check, "web_search", lambda q, **k: [])
    evidence = contact_check.check_contact(scam_claims, context)
    entry = by_id(evidence, "l2_contact_intl_prefix")
    assert entry.status == "fail"
    assert context["intl_contact_flag"] is True
    assert entry.raw_data["foreign"][0]["dial_code"] == "44"


def test_contact_indian_number_passes(monkeypatch, legit_claims, context):
    monkeypatch.setattr(contact_check, "web_search", lambda q, **k: [])
    entry = by_id(contact_check.check_contact(legit_claims, context), "l2_contact_intl_prefix")
    assert entry.status == "pass"
    assert context["intl_contact_flag"] is False


def test_contact_matches_published_customer_care(monkeypatch, legit_claims, context):
    monkeypatch.setattr(
        contact_check, "web_search",
        lambda q, **k: make_results(
            ("Contact Nimbus Analytics Private Limited",
             "https://www.nimbusanalytics.in/contact",
             "Reach Nimbus Analytics Private Limited on +91-44-40012345"),
        ),
    )
    entry = by_id(contact_check.check_contact(legit_claims, context), "l2_contact_public_match")
    assert entry.status == "pass"


def test_contact_public_match_unavailable_offline(monkeypatch, legit_claims, context):
    monkeypatch.setattr(contact_check, "web_search", offline_search)
    entry = by_id(contact_check.check_contact(legit_claims, context), "l2_contact_public_match")
    assert entry.status == "unavailable"


# --------------------------------------------------------------------------
# 2.5 HR email
# --------------------------------------------------------------------------

def test_hr_email_free_provider_with_company_domain_fails(monkeypatch, scam_claims, context):
    monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: True)
    evidence = hr_email_check.check_hr_email(scam_claims, context)
    assert by_id(evidence, "l2_email_domain_match").status == "fail"
    assert by_id(evidence, "l2_email_free_provider").status == "fail"
    assert context["email_domain_mismatch"] is True


def test_hr_email_free_provider_without_company_domain_is_warning(monkeypatch, scam_claims, context):
    claims = scam_claims.model_copy(update={"website_url": None})
    monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: True)
    evidence = hr_email_check.check_hr_email(claims, context)
    entry = by_id(evidence, "l2_email_free_provider")
    assert entry.status == "warning", "informal recruiters must not be punished as fraud"


def test_hr_email_matching_company_domain_passes(monkeypatch, legit_claims, context):
    monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: True)
    evidence = hr_email_check.check_hr_email(legit_claims, context)
    assert by_id(evidence, "l2_email_domain_match").status == "pass"
    assert by_id(evidence, "l2_email_free_provider").status == "pass"
    assert by_id(evidence, "l2_email_mx").status == "pass"
    assert context["email_domain_mismatch"] is False


def test_hr_email_sibling_corporate_domain_warns_not_fails(monkeypatch, legit_claims, context):
    """Large employers run sibling domains; that is a confirm-it, not a verdict."""
    claims = legit_claims.model_copy(
        update={"company_name": "Zoho Corporation", "website_url": "https://www.zoho.com",
                "recruiter_email": "careers@zohocorp.com"}
    )
    monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: True)
    entry = by_id(hr_email_check.check_hr_email(claims, context), "l2_email_domain_match")
    assert entry.status == "warning"
    assert context["email_domain_mismatch"] is False, "must not feed the new-domain floor"


def test_hr_email_unrelated_domain_still_fails(monkeypatch, legit_claims, context):
    claims = legit_claims.model_copy(
        update={"recruiter_email": "hr@fast-hiring-jobs24.xyz"}
    )
    monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: True)
    entry = by_id(hr_email_check.check_hr_email(claims, context), "l2_email_domain_match")
    assert entry.status == "fail"
    assert context["email_domain_mismatch"] is True


def test_hr_email_without_mx_fails(monkeypatch, legit_claims, context):
    monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: False)
    entry = by_id(hr_email_check.check_hr_email(legit_claims, context), "l2_email_mx")
    assert entry.status == "fail"


def test_hr_email_dns_outage_is_unavailable(monkeypatch, legit_claims, context):
    def boom(host, **kwargs):
        raise DnsUnavailable("Timeout: resolver unreachable")

    monkeypatch.setattr(hr_email_check, "has_mx", boom)
    entry = by_id(hr_email_check.check_hr_email(legit_claims, context), "l2_email_mx")
    assert entry.status == "unavailable"
    assert entry.confidence == 0.0


def test_hr_email_falls_back_to_address_in_posting_text(monkeypatch, scam_claims, context):
    claims = scam_claims.model_copy(update={"recruiter_email": None})
    monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: True)
    hr_email_check.check_hr_email(claims, context)
    assert context["recruiter_email"] == "jobsoffers2026.apex@gmail.com"


# --------------------------------------------------------------------------
# level report
# --------------------------------------------------------------------------

def test_level2_report_scores_scam_below_legit(monkeypatch, legit_claims, scam_claims):
    def patch_all(target_company_verified: bool, domain_days: int, mx: bool):
        monkeypatch.setattr(existence_check, "web_search",
                            (lambda q, **k: make_results(
                                ("Nimbus Analytics Private Limited",
                                 "https://en.wikipedia.org/wiki/Nimbus_Analytics",
                                 "Nimbus Analytics Private Limited is an analytics firm"))
                             ) if target_company_verified else (lambda q, **k: []))
        monkeypatch.setattr(contact_check, "web_search", lambda q, **k: [])
        monkeypatch.setattr(location_check, "web_search", lambda q, **k: [])
        monkeypatch.setattr(website_check, "domain_age", lambda d, **k: age(domain_days, d))
        for module in (website_check, location_check):
            monkeypatch.setattr(
                module, "fetch",
                lambda url, *a, **k: html_page(
                    "Nimbus Analytics Private Limited, Guindy, Chennai " + "x" * 400
                ),
            )
        monkeypatch.setattr(hr_email_check, "has_mx", lambda host, **k: mx)

    patch_all(True, 900, True)
    legit_report = run_level2(legit_claims, {})

    patch_all(False, 9, True)
    scam_report = run_level2(scam_claims, {})

    assert legit_report.level == 2
    assert legit_report.level_score > scam_report.level_score
    assert scam_report.checks_failed >= 3
    assert legit_report.checks_run == len(legit_report.evidence)


def test_level2_survives_total_network_outage(monkeypatch, scam_claims):
    for module in (location_check, existence_check, contact_check):
        monkeypatch.setattr(module, "web_search", offline_search)
    for module in (location_check, website_check):
        monkeypatch.setattr(module, "fetch", offline_fetch)

    def boom_whois(domain, **kwargs):
        raise WhoisUnavailable("offline")

    def boom_dns(host, **kwargs):
        raise DnsUnavailable("offline")

    monkeypatch.setattr(website_check, "domain_age", boom_whois)
    monkeypatch.setattr(hr_email_check, "has_mx", boom_dns)

    report = run_level2(scam_claims, {})
    assert report.level_score >= 0
    assert report.checks_unavailable >= 4
    assert isinstance(report.evidence, list) and report.evidence


def test_search_unavailable_is_an_exception_type():
    assert issubclass(SearchUnavailable, RuntimeError)


@pytest.mark.parametrize("phone,expected_code", [
    ("+91-9876543210", "91"),
    ("+919876543210", "91"),
    ("+44 7911 123456", "44"),
    ("+60 12-345 6789", "60"),
])
def test_phone_dial_code_extraction(phone, expected_code, legit_claims):
    claims = legit_claims.model_copy(update={"recruiter_phone": phone, "posting_text": ""})
    phones = contact_check._extract_phones(claims)
    assert phones and phones[0]["dial_code"] == expected_code
