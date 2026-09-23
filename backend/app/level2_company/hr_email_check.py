"""Level 2.5 - HR details and recruiter email verification.

Three signals from one address:

* ``l2_email_domain_match``  - does the recruiter write from the company domain?
* ``l2_email_free_provider`` - is "corporate HR" using consumer webmail?
* ``l2_email_mx``            - can the domain even receive mail?

Fairness rule: a free-mail address only fails when the company *does* have a
domain of its own to write from. Small and informal but legitimate recruiters
are not punished for having no corporate mail server.
"""

from __future__ import annotations

from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.domain_utils import parse_domain
from ..shared.email_utils import (
    DnsUnavailable,
    email_domain,
    email_host,
    extract_emails,
    has_mx,
    is_disposable_provider,
    is_free_provider,
)
from ..shared.fuzzy_match import name_matches_domain

LEVEL = 2
LABELS = {
    "l2_email_domain_match": "Recruiter Email Domain Match",
    "l2_email_free_provider": "Recruiter Email Provider Type",
    "l2_email_mx": "Recruiter Email Deliverability (MX)",
}

DOMAIN_MATCH_RATIO = 85.0


def check_hr_email(claims: ExtractedClaims, context: dict[str, Any]) -> list[EvidenceItem]:
    email = (claims.recruiter_email or "").strip().lower()
    if not email:
        candidates = extract_emails(claims.posting_text)
        email = candidates[0] if candidates else ""

    if not email:
        context["email_domain_mismatch"] = False
        reason = (
            "The posting carries no recruiter email address, so no mailbox checks "
            "could run (missing contact details are reported by Level 1)."
        )
        return [
            item(LEVEL, cid, label, "unavailable", reason,
                 raw_data={"reason": "no recruiter email"}, confidence=0.0)
            for cid, label in LABELS.items()
        ]

    domain = email_domain(email)
    host = email_host(email)
    context["recruiter_email"] = email
    context["recruiter_email_domain"] = domain

    company_domain = parse_domain(claims.website_url).registered_domain or None
    free = is_free_provider(domain)
    disposable = is_disposable_provider(domain)

    return [
        _domain_match_item(claims, email, domain, company_domain, free, context),
        _provider_item(email, domain, company_domain, free, disposable),
        _mx_item(email, domain, host),
    ]


def _domain_match_item(
    claims: ExtractedClaims,
    email: str,
    domain: str,
    company_domain: str | None,
    free: bool,
    context: dict[str, Any],
) -> EvidenceItem:
    cid = "l2_email_domain_match"
    raw = {"email": email, "email_domain": domain, "company_domain": company_domain}

    if company_domain:
        if domain == company_domain:
            context["email_domain_mismatch"] = False
            return item(LEVEL, cid, LABELS[cid], "pass",
                        f"The recruiter writes from the company's own domain "
                        f"({company_domain}).", raw_data=raw)

        # Large employers legitimately run sibling domains ("zohocorp.com" beside
        # "zoho.com"), so a domain that still carries the company's name is a
        # warning to confirm, not a fabrication verdict - and it does not feed
        # the new-domain hard floor.
        brand_ratio = max(
            name_matches_domain(claims.company_name, parse_domain(domain).label),
            name_matches_domain(parse_domain(company_domain).label, parse_domain(domain).label),
        )
        raw["brand_match_ratio"] = round(brand_ratio, 1)
        if not free and brand_ratio >= DOMAIN_MATCH_RATIO:
            context["email_domain_mismatch"] = False
            return item(
                LEVEL, cid, LABELS[cid], "warning",
                f"The recruiter writes from '{domain}' rather than the website's "
                f"'{company_domain}'. The two names match closely, which is normal "
                "for a sibling corporate domain, but is worth confirming.",
                raw_data=raw, confidence=0.7,
            )

        context["email_domain_mismatch"] = True
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"The recruiter email is on '{domain}' while the company's website is "
            f"'{company_domain}'. A genuine HR contact writes from the company domain.",
            raw_data=raw,
        )

    # No website to compare against: fall back to comparing the mail domain with
    # the company name itself, so "hr@apexglobal.in" still counts for something.
    ratio = name_matches_domain(claims.company_name, parse_domain(domain).label)
    raw["name_match_ratio"] = round(ratio, 1)
    if free:
        context["email_domain_mismatch"] = True
        return item(
            LEVEL, cid, LABELS[cid], "warning",
            f"The recruiter uses a consumer mailbox ({domain}) and the posting "
            "gives no company website to compare it against.",
            raw_data=raw, confidence=0.7,
        )
    if ratio >= DOMAIN_MATCH_RATIO:
        context["email_domain_mismatch"] = False
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            f"No company website was given, but the recruiter's domain '{domain}' "
            f"matches the company name (similarity {ratio:.0f}/100).", raw_data=raw,
        )
    context["email_domain_mismatch"] = True
    return item(
        LEVEL, cid, LABELS[cid], "warning",
        f"The recruiter's domain '{domain}' bears little resemblance to "
        f"'{claims.company_name or 'the company named'}' (similarity {ratio:.0f}/100) "
        "and there is no official website to check it against.",
        raw_data=raw, confidence=0.8,
    )


def _provider_item(
    email: str, domain: str, company_domain: str | None, free: bool, disposable: bool
) -> EvidenceItem:
    cid = "l2_email_free_provider"
    raw = {"email": email, "email_domain": domain, "company_domain": company_domain,
           "free_provider": free, "disposable_provider": disposable}

    if disposable:
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"The recruiter uses a disposable mailbox service ({domain}), which "
            "exists specifically to be untraceable.",
            raw_data=raw,
        )
    if not free:
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            f"The recruiter email is on a private domain ({domain}), not consumer "
            "webmail.", raw_data=raw,
        )
    if company_domain:
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"HR is writing from free consumer webmail ({domain}) even though the "
            f"company operates its own domain ({company_domain}).",
            raw_data=raw,
        )
    return item(
        LEVEL, cid, LABELS[cid], "warning",
        f"HR is writing from free consumer webmail ({domain}). The company has no "
        "verified domain to compare against, so this is treated as a flag rather "
        "than proof - small and informal employers do this legitimately.",
        raw_data=raw, confidence=0.8,
    )


def _mx_item(email: str, domain: str, host: str) -> EvidenceItem:
    cid = "l2_email_mx"
    lookup_host = host or domain
    raw = {"email": email, "mail_host": lookup_host}
    try:
        deliverable = has_mx(lookup_host)
    except DnsUnavailable as exc:
        raw["error"] = str(exc)
        return item(
            LEVEL, cid, LABELS[cid], "unavailable",
            f"DNS could not be queried for {lookup_host}, so deliverability is unknown.",
            raw_data=raw, confidence=0.0,
        )

    raw["has_mx"] = deliverable
    if deliverable:
        return item(LEVEL, cid, LABELS[cid], "pass",
                    f"{lookup_host} publishes mail records and can receive email.",
                    raw_data=raw)
    return item(
        LEVEL, cid, LABELS[cid], "fail",
        f"{lookup_host} publishes no mail records at all - the address cannot "
        "receive replies, which points to a fabricated contact.",
        raw_data=raw,
    )
