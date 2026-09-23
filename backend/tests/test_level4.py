"""Level 4 check tests - external evidence."""

from __future__ import annotations

from app.level4_evidence import freshness_checker, review_scraper
from app.level4_evidence.orchestrator import run_level4
from tests.conftest import make_results, offline_search
from tests.test_level2 import by_id


def listing(url: str, snippet: str, title: str = "Junior Data Entry & Back Office Assistant") -> dict:
    return {"title": title, "url": url, "snippet": snippet}


# --------------------------------------------------------------------------
# 4.1 reviews and complaints
# --------------------------------------------------------------------------

def test_multiple_independent_scam_reports_fail(monkeypatch, scam_claims, context):
    def fake_search(query, **kwargs):
        if "scam" in query:
            return make_results(
                ("Apex Global Innovators Inc. scam alert",
                 "https://www.reddit.com/r/india/comments/abc",
                 "Apex Global Innovators Inc. took my registration fee, clear scam, 2 months ago"),
                ("Is Apex Global Innovators Inc. fraud?",
                 "https://www.quora.com/Is-Apex-Global-Innovators-fraud",
                 "Apex Global Innovators Inc. is a fraud, they asked for money 12 Mar 2025"),
            )
        return []

    monkeypatch.setattr(review_scraper, "web_search", fake_search)
    entry = by_id(review_scraper.check_reviews(scam_claims, context), "l4_fraud_mentions")
    assert entry.status == "fail"
    assert len(entry.raw_data["independent_sources"]) >= 2


def test_single_complaint_is_a_warning(monkeypatch, scam_claims, context):
    def fake_search(query, **kwargs):
        if "scam" in query:
            return make_results(
                ("Apex Global Innovators Inc. complaint",
                 "https://www.reddit.com/r/india/comments/abc",
                 "Apex Global Innovators Inc. never paid me, filing a complaint"),
            )
        return []

    monkeypatch.setattr(review_scraper, "web_search", fake_search)
    entry = by_id(review_scraper.check_reviews(scam_claims, context), "l4_fraud_mentions")
    assert entry.status == "warning"


def test_quoted_snippet_stays_short(monkeypatch, scam_claims, context):
    def fake_search(query, **kwargs):
        if "scam" in query:
            return make_results(
                ("Apex Global Innovators Inc. scam",
                 "https://www.reddit.com/r/india/comments/abc",
                 " ".join(f"word{i}" for i in range(80)) + " Apex Global Innovators Inc. scam"),
                ("Apex Global Innovators Inc. fraud",
                 "https://www.quora.com/q",
                 "Apex Global Innovators Inc. fraud reported by many candidates"),
            )
        return []

    monkeypatch.setattr(review_scraper, "web_search", fake_search)
    entry = by_id(review_scraper.check_reviews(scam_claims, context), "l4_fraud_mentions")
    for mention in entry.raw_data["mentions"]:
        assert len(mention["quote"].split()) <= review_scraper.MAX_QUOTED_WORDS


def test_clean_review_footprint_passes(monkeypatch, legit_claims, context):
    def fake_search(query, **kwargs):
        if "scam" in query:
            return []
        return make_results(
            ("Nimbus Analytics Private Limited Reviews | AmbitionBox",
             "https://www.ambitionbox.com/reviews/nimbus-analytics-reviews",
             "Nimbus Analytics Private Limited rated 4.1 by 120 employees"),
        )

    monkeypatch.setattr(review_scraper, "web_search", fake_search)
    evidence = review_scraper.check_reviews(legit_claims, context)
    assert by_id(evidence, "l4_fraud_mentions").status == "pass"
    assert by_id(evidence, "l4_review_presence").status == "pass"


def test_no_review_footprint_is_a_warning(monkeypatch, scam_claims, context):
    monkeypatch.setattr(review_scraper, "web_search", lambda q, **k: [])
    entry = by_id(review_scraper.check_reviews(scam_claims, context), "l4_review_presence")
    assert entry.status == "warning"


def test_reviews_offline_are_unavailable(monkeypatch, scam_claims, context):
    monkeypatch.setattr(review_scraper, "web_search", offline_search)
    evidence = review_scraper.check_reviews(scam_claims, context)
    assert {e.status for e in evidence} == {"unavailable"}
    assert all(e.confidence == 0.0 for e in evidence)


# --------------------------------------------------------------------------
# 4.2 freshness and repeat posting
# --------------------------------------------------------------------------

def test_recycled_posting_over_months_fails(scam_claims, context):
    copied = scam_claims.posting_text[:200]
    context["cross_platform_results"] = [
        listing("https://www.naukri.com/a", f"{copied} posted 5 days ago"),
        listing("https://www.linkedin.com/b", f"{copied} posted 8 months ago"),
    ]
    entry = by_id(freshness_checker.check_freshness(scam_claims, context), "l4_repost_pattern")
    assert entry.status == "fail"
    assert entry.raw_data["age_spread_days"] >= freshness_checker.REPOST_SPREAD_DAYS


def test_template_reuse_across_many_sites_fails(scam_claims, context):
    copied = scam_claims.posting_text[:200]
    context["cross_platform_results"] = [
        listing("https://www.naukri.com/a", copied),
        listing("https://www.linkedin.com/b", copied),
        listing("https://www.indeed.com/c", copied),
    ]
    entry = by_id(freshness_checker.check_freshness(scam_claims, context), "l4_repost_pattern")
    assert entry.status == "fail"
    assert entry.raw_data["duplicate_copies"] == 3


def test_missing_dates_report_unavailable_not_warning(legit_claims, context):
    context["cross_platform_results"] = [
        listing("https://www.naukri.com/a", "Analyst opening in Chennai", "Junior Data Analyst"),
    ]
    entry = by_id(freshness_checker.check_freshness(legit_claims, context), "l4_listing_age")
    assert entry.status == "unavailable"
    assert entry.confidence == 0.0


def test_fresh_listing_passes(legit_claims, context):
    context["cross_platform_results"] = [
        listing("https://www.naukri.com/a", "Junior Data Analyst, Chennai, posted 4 days ago",
                "Junior Data Analyst"),
    ]
    entry = by_id(freshness_checker.check_freshness(legit_claims, context), "l4_listing_age")
    assert entry.status == "pass"
    assert entry.raw_data["newest_days"] == 4


def test_stale_listing_is_a_warning(legit_claims, context):
    context["cross_platform_results"] = [
        listing("https://www.naukri.com/a", "Junior Data Analyst posted 2024-01-05",
                "Junior Data Analyst"),
    ]
    entry = by_id(freshness_checker.check_freshness(legit_claims, context), "l4_listing_age")
    assert entry.status == "warning"


def test_freshness_without_any_listings_is_unavailable(legit_claims, context):
    evidence = freshness_checker.check_freshness(legit_claims, context)
    assert {e.status for e in evidence} == {"unavailable"}


def test_freshness_reuses_level3_results_without_searching(monkeypatch, legit_claims, context):
    """Level 4.2 must not run its own search - it reuses Level 3.1's listings."""
    assert not hasattr(freshness_checker, "web_search")


# --------------------------------------------------------------------------
# level report
# --------------------------------------------------------------------------

def test_level4_report_and_offline_behaviour(monkeypatch, scam_claims):
    monkeypatch.setattr(review_scraper, "web_search", offline_search)
    report = run_level4(scam_claims, {})
    assert report.level == 4
    assert report.checks_unavailable == report.checks_run
    assert report.degraded is True
    assert report.level_score == 100.0, "unavailable lookups must not invent guilt"
