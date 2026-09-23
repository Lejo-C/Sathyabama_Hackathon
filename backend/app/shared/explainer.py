"""Turn an evidence list into a short plain-English summary.

The LLM **explains**, it never decides. The score handed to this module is
already final: Groq only writes prose around evidence that deterministic checks
produced. If Groq is missing, slow or erroring, a template summary is generated
from the same evidence so the product never goes blank on stage.
"""

from __future__ import annotations

import logging
import os

import requests

from ..core.schemas import EvidenceItem

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TIMEOUT = 6.0
DEFAULT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are the explanation layer of PRAHARI, a job-fraud detection system. "
    "You are given a verification score and a list of deterministic check "
    "results. Write 2-3 plain-English sentences for a job seeker: what was "
    "verified, what raised concern, and what it means for them. "
    "Never invent evidence, never contradict the score, never add advice that "
    "the evidence does not support. No bullet points, no headings."
)


def _groq_api_key() -> str | None:
    """Read the Groq key from the environment (never hardcoded, never logged)."""
    for name in ("GROQ_API_KEY", "GROQ_KEY", "VITE_GROQ_API_KEY"):
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _severity_sort(item: EvidenceItem) -> tuple[int, float]:
    order = {"fail": 0, "warning": 1, "unavailable": 2, "pass": 3}
    return order.get(item.status, 4), -item.risk_weight


def build_template_summary(evidence: list[EvidenceItem], score: float) -> str:
    """Deterministic fallback summary - always available, never blank."""
    fails = [e for e in evidence if e.status == "fail"]
    warnings = [e for e in evidence if e.status == "warning"]
    unavailable = [e for e in evidence if e.status == "unavailable"]

    if score >= 75:
        verdict = "Background verification did not surface material fraud signals"
    elif score >= 50:
        verdict = "Background verification surfaced some concerns worth checking"
    elif score >= 25:
        verdict = "Background verification surfaced serious concerns"
    else:
        verdict = "Background verification strongly indicates a fraudulent posting"

    parts = [f"{verdict} (verification score {score:.0f}/100, lower is riskier)."]

    top = sorted(fails, key=_severity_sort)[:3]
    if top:
        detail = "; ".join(f"{item.label}: {item.finding}" for item in top)
        parts.append(f"Failed checks - {detail}.")
    elif warnings:
        detail = "; ".join(f"{item.label}: {item.finding}" for item in warnings[:2])
        parts.append(f"Unconfirmed items - {detail}.")

    if unavailable:
        parts.append(
            f"{len(unavailable)} check(s) could not be completed because an "
            "external lookup was unreachable, so absence of a flag there is not "
            "proof of legitimacy."
        )
    return " ".join(parts)


def _evidence_digest(evidence: list[EvidenceItem], limit: int = 14) -> str:
    rows = sorted(evidence, key=_severity_sort)[:limit]
    return "\n".join(
        f"- [L{item.level}] {item.label} ({item.status}): {item.finding}"
        for item in rows
    )


def explain(
    evidence: list[EvidenceItem],
    score: float,
    company_name: str | None = None,
    timeout: float = GROQ_TIMEOUT,
) -> tuple[str, str]:
    """Return ``(summary, source)`` where source is ``"groq"`` or ``"template"``."""

    fallback = build_template_summary(evidence, score)
    api_key = _groq_api_key()
    if not api_key:
        logger.info("GROQ_API_KEY not set - using template summary")
        return fallback, "template"

    user_prompt = (
        f"Company under review: {company_name or 'not stated in the posting'}\n"
        f"Verification score: {score:.0f}/100 (lower = riskier)\n"
        f"Deterministic check results:\n{_evidence_digest(evidence)}"
    )

    try:
        response = requests.post(
            GROQ_URL,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("GROQ_MODEL", DEFAULT_MODEL),
                "temperature": 0.2,
                "max_tokens": 220,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        if response.status_code >= 400:
            logger.warning("Groq returned HTTP %s - falling back", response.status_code)
            return fallback, "template"

        text = response.json()["choices"][0]["message"]["content"].strip()
        return (text, "groq") if text else (fallback, "template")
    except Exception as exc:
        logger.warning("Groq explanation failed (%s) - falling back", exc)
        return fallback, "template"
