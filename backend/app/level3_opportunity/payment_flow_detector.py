"""Level 3.3 - Payment demanded during the registration / application flow.

**How this differs from Level 1.** Level 1 reads the raw posting text for
payment *language* ("registration fee", "refundable deposit") as a writing-style
signal. This check looks for a payment *instrument or instruction inside the
application flow itself*: a UPI VPA, a bank account with an IFSC, a QR-code
request, a payment-gateway collect link, or a "pay before joining" instruction
served on the application page.

The split is enforced mechanically:

* payment **instruments** (UPI / account / IFSC / QR / gateway links) count
  wherever they appear, including in the posting text, because an actual payee
  handle is flow evidence, not wording;
* payment **language** only counts when it is served by the application URL, so
  the same sentence in the posting body is never scored twice across levels.

A confirmed instrument sets ``payment_to_individual`` in the shared context,
which the orchestrator turns into a non-negotiable hard floor.
"""

from __future__ import annotations

import re
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims
from ..shared.domain_utils import parse_domain
from ..shared.web_fetch import fetch

LEVEL = 3
LABELS = {
    "l3_payment_instrument": "Payment Instrument in Application Flow",
    "l3_payment_gateway_link": "Payment Gateway Link in Application Flow",
    "l3_payment_flow_instruction": "Payment Instruction on Application Page",
}

# A UPI handle looks like an email without a dotted TLD: "name@okhdfcbank".
UPI_VPA_RE = re.compile(r"\b([a-zA-Z0-9][\w.\-]{2,49})@([a-zA-Z]{2,20})\b(?!\.)")
UPI_HANDLES = {
    "okhdfcbank", "oksbi", "okaxis", "okicici", "ybl", "ibl", "axl", "upi", "paytm",
    "apl", "airtel", "freecharge", "jio", "sbi", "hdfcbank", "icici", "axisbank",
    "barodampay", "kotak", "yesbank", "idfcbank", "fbl", "indus", "dbs", "rbl",
}
UPI_DEEPLINK_RE = re.compile(r"upi://[^\s\"'<>]+", re.I)
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
ACCOUNT_CONTEXT_RE = re.compile(
    r"(?:a/?c(?:count)?(?:\s*(?:no|number|#))?\s*[:\-]?\s*)(\d{9,18})", re.I
)
QR_RE = re.compile(r"\b(scan\s+(?:the\s+)?qr|qr\s*code|scanner\s+below)\b", re.I)

GATEWAY_DOMAINS = {
    "razorpay.com": "Razorpay",
    "rzp.io": "Razorpay",
    "instamojo.com": "Instamojo",
    "imjo.in": "Instamojo",
    "paytm.me": "Paytm",
    "p.paytm.me": "Paytm",
    "phonepe.com": "PhonePe",
    "pages.razorpay.com": "Razorpay Payment Page",
    "cashfree.com": "Cashfree",
    "payu.in": "PayU",
    "gpay.app.goo.gl": "Google Pay",
}
URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.I)

# Instruction language. Only scored when served by the application flow.
FLOW_INSTRUCTION_RE = re.compile(
    r"\b(registration\s+fee|processing\s+fee|security\s+deposit|refundable\s+deposit|"
    r"training\s+fee|onboarding\s+fee|pay\s+(?:before|prior\s+to)\s+(?:joining|onboarding|interview)|"
    r"deposit\s+(?:of\s+)?(?:₹|rs\.?|inr)|payment\s+screenshot|"
    r"transfer\s+the\s+amount)\b",
    re.I,
)


def check_payment_flow(
    claims: ExtractedClaims, context: dict[str, Any]
) -> list[EvidenceItem]:
    application_text, fetch_meta = _load_application_page(claims)
    instrument_sources = {
        "posting_text": claims.posting_text or "",
        "application_page": application_text,
    }

    instruments = _find_instruments(instrument_sources)
    gateways = _find_gateway_links(instrument_sources, claims, context)
    evidence = [
        _instrument_item(instruments, fetch_meta, context),
        _gateway_item(gateways, fetch_meta),
    ]

    if application_text:
        evidence.append(_flow_instruction_item(application_text, fetch_meta))
    else:
        evidence.append(
            item(
                LEVEL, "l3_payment_flow_instruction",
                LABELS["l3_payment_flow_instruction"], "unavailable",
                "No application URL was supplied (or it could not be fetched), so "
                "the application flow itself could not be inspected. Payment wording "
                "inside the posting text is scored by Level 1, not here.",
                raw_data=fetch_meta, confidence=0.0,
            )
        )
    return evidence


def _load_application_page(claims: ExtractedClaims) -> tuple[str, dict[str, Any]]:
    if not claims.application_url:
        return "", {"application_url": None, "fetched": False,
                    "reason": "no application_url supplied"}
    result = fetch(claims.application_url)
    if not result.ok:
        return "", {"application_url": claims.application_url, "fetched": False,
                    "status_code": result.status_code, "error": result.error}
    text = result.visible_text
    raw_links = " ".join(result.links())
    return f"{text} {raw_links}", {
        "application_url": claims.application_url,
        "fetched": True,
        "status_code": result.status_code,
        "text_length": len(text),
    }


def _find_instruments(sources: dict[str, str]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for origin, text in sources.items():
        if not text:
            continue

        for handle, bank in UPI_VPA_RE.findall(text):
            if bank.lower() in UPI_HANDLES:
                found.append({"type": "upi_vpa", "value": f"{handle}@{bank}",
                              "origin": origin})
        for link in UPI_DEEPLINK_RE.findall(text):
            found.append({"type": "upi_deeplink", "value": link[:120], "origin": origin})
        for ifsc in IFSC_RE.findall(text):
            found.append({"type": "bank_ifsc", "value": ifsc, "origin": origin})
        for account in ACCOUNT_CONTEXT_RE.findall(text):
            found.append({"type": "bank_account", "value": _mask(account),
                          "origin": origin})
        if QR_RE.search(text):
            found.append({"type": "qr_request",
                          "value": QR_RE.search(text).group(0), "origin": origin})

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in found:
        key = (entry["type"], entry["value"])
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    return deduped


def _find_gateway_links(
    sources: dict[str, str], claims: ExtractedClaims, context: dict[str, Any]
) -> list[dict[str, str]]:
    company_domain = context.get("verified_domain") or parse_domain(claims.website_url).registered_domain
    links: list[dict[str, str]] = []
    for origin, text in sources.items():
        for url in URL_RE.findall(text or ""):
            domain = parse_domain(url).registered_domain
            provider = GATEWAY_DOMAINS.get(domain)
            if not provider:
                continue
            links.append({
                "provider": provider,
                "url": url[:160],
                "origin": origin,
                "on_company_domain": str(bool(company_domain and company_domain in url)),
            })
    return links


def _instrument_item(
    instruments: list[dict[str, str]], fetch_meta: dict[str, Any], context: dict[str, Any]
) -> EvidenceItem:
    cid = "l3_payment_instrument"
    context["payment_to_individual"] = bool(instruments)
    context["payment_instruments"] = instruments

    if not instruments:
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            "No UPI handle, bank account, IFSC code or QR request was found anywhere "
            "in the application flow.",
            raw_data={"instruments": [], **fetch_meta},
            confidence=1.0 if fetch_meta.get("fetched") else 0.6,
        )

    kinds = sorted({entry["type"] for entry in instruments})
    return item(
        LEVEL, cid, LABELS[cid], "fail",
        "The application flow carries a direct payment instrument "
        f"({', '.join(kinds)}): money is being collected into a personal account. "
        "No legitimate employer asks a candidate to pay to be hired.",
        raw_data={"instruments": instruments, **fetch_meta},
    )


def _gateway_item(gateways: list[dict[str, str]], fetch_meta: dict[str, Any]) -> EvidenceItem:
    cid = "l3_payment_gateway_link"
    if not gateways:
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            "No payment-gateway collect link appears in the application flow.",
            raw_data={"gateway_links": [], **fetch_meta},
            confidence=1.0 if fetch_meta.get("fetched") else 0.6,
        )

    providers = sorted({entry["provider"] for entry in gateways})
    off_domain = [g for g in gateways if g["on_company_domain"] == "False"]
    if off_domain:
        return item(
            LEVEL, cid, LABELS[cid], "fail",
            f"The application flow sends candidates to a {', '.join(providers)} "
            "collect link hosted outside the employer's own checkout - the standard "
            "way fee scams take money.",
            raw_data={"gateway_links": gateways, **fetch_meta},
        )
    return item(
        LEVEL, cid, LABELS[cid], "warning",
        f"A {', '.join(providers)} payment link appears in the application flow on "
        "the company's own domain. Verify why an applicant is being charged at all.",
        raw_data={"gateway_links": gateways, **fetch_meta}, confidence=0.8,
    )


def _flow_instruction_item(text: str, fetch_meta: dict[str, Any]) -> EvidenceItem:
    cid = "l3_payment_flow_instruction"
    matches = sorted({m.group(0).lower() for m in FLOW_INSTRUCTION_RE.finditer(text)})
    if not matches:
        return item(
            LEVEL, cid, LABELS[cid], "pass",
            "The application page asks for no fee, deposit or payment screenshot.",
            raw_data={"matches": [], **fetch_meta},
        )
    return item(
        LEVEL, cid, LABELS[cid], "fail",
        "The application page itself instructs candidates to pay: "
        f"{', '.join(repr(m) for m in matches[:4])}. This is a live payment demand in "
        "the hiring flow, separate from any fee wording in the advert.",
        raw_data={"matches": matches, **fetch_meta},
    )


def _mask(account: str) -> str:
    return f"{'*' * max(0, len(account) - 4)}{account[-4:]}"
