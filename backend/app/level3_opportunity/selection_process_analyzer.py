"""Level 3.4 - Recruitment / selection process analysis.

Legitimate hiring has a process: screening, an interview, a written offer. Scam
postings compress or delete it - "no interview needed", "selection within 24
hours", "join immediately", "contact on WhatsApp only".

Each matched pattern becomes its **own** evidence item rather than one blended
blob, so the explainer can cite the specific phrase and a reviewer can see
exactly what triggered the flag. This check is offline-only: it needs no network
and therefore keeps working when the venue wifi does not.
"""

from __future__ import annotations

import re
from typing import Any

from ..core.runner import item
from ..core.schemas import EvidenceItem, ExtractedClaims

LEVEL = 3
WEIGHT_KEY = "l3_selection_process"

# (slug, label, regex, why it matters)
PROCESS_PATTERNS: list[tuple[str, str, str, str]] = [
    (
        "no_interview", "No Interview Required",
        r"\b(no\s+interview|without\s+(?:any\s+)?interview|interview\s+not\s+required|"
        r"direct\s+joining)\b",
        "Skipping assessment entirely means the employer is not actually selecting "
        "anyone - the product being sold is the application itself.",
    ),
    (
        "instant_selection", "Instant / Guaranteed Selection",
        r"\b(instant\s+selection|immediate\s+selection|selected\s+immediately|"
        r"guaranteed\s+(?:job|placement|selection)|100%\s+(?:job|placement))\b",
        "Guaranteed selection before any evaluation is a bait used to move the "
        "candidate to a payment step.",
    ),
    (
        "fast_decision", "Selection Promised Within Hours",
        r"\b(selection\s+within\s+\d+\s*(?:hours|hrs|days)|offer\s+letter\s+within\s+"
        r"\d+\s*(?:hours|hrs)|same\s+day\s+(?:offer|selection|joining))\b",
        "A decision window measured in hours removes the time a candidate would "
        "need to verify the employer.",
    ),
    (
        "whatsapp_only", "WhatsApp / Telegram Only Channel",
        r"\b(whatsapp\s+only|only\s+on\s+whatsapp|contact\s+(?:us\s+)?(?:on|via|through)\s+"
        r"whatsapp|telegram\s+(?:only|id|@)|dm\s+on\s+telegram|hr\s+whatsapp)\b",
        "Moving hiring onto a personal messaging app leaves no auditable record "
        "and is the dominant channel in documented Indian recruitment scams.",
    ),
    (
        "join_immediately", "Immediate Joining Pressure",
        r"\b(join\s+immediately|immediate\s+joiner[s]?\s+only|start\s+today|"
        r"joining\s+today)\b",
        "Immediate-joining pressure is used to rush candidates past verification.",
    ),
    (
        "no_experience_high_pay", "No Skills Needed For High Pay",
        r"\b(no\s+(?:prior\s+)?(?:experience|technical\s+background|skills?)\s+"
        r"(?:needed|required)|anyone\s+can\s+apply|no\s+qualification\s+required)\b",
        "Pairing zero requirements with a high payout is the classic bait metric "
        "of task-and-fee scams.",
    ),
    (
        "personal_channel_only", "Apply Outside The Platform",
        r"\b(do\s+not\s+reply\s+(?:to\s+)?(?:this|the)\s+(?:job\s+)?portal|"
        r"apply\s+only\s+(?:via|through)\s+(?:whatsapp|telegram|email)|"
        r"send\s+(?:your\s+)?(?:resume|cv)\s+(?:directly\s+)?to)\b",
        "Pulling applicants off the platform removes the platform's fraud "
        "reporting and moderation from the loop.",
    ),
]

_COMPILED = [
    (slug, label, re.compile(pattern, re.I), rationale)
    for slug, label, pattern, rationale in PROCESS_PATTERNS
]

CONTEXT_WINDOW = 90


def check_selection_process(
    claims: ExtractedClaims, context: dict[str, Any]
) -> list[EvidenceItem]:
    text = " ".join(
        filter(None, [claims.posting_text or "", context.get("application_page_text", "")])
    )
    if not text.strip():
        return [
            item(
                LEVEL, "l3_selection_process", "Recruitment Process Analysis",
                "unavailable",
                "No posting text was supplied, so the selection process could not be "
                "analysed.",
                raw_data={"reason": "empty posting text"}, weight_key=WEIGHT_KEY,
                confidence=0.0,
            )
        ]

    evidence: list[EvidenceItem] = []
    for slug, label, pattern, rationale in _COMPILED:
        match = pattern.search(text)
        if not match:
            continue
        evidence.append(
            item(
                LEVEL, f"l3_process_{slug}", f"Selection Process: {label}", "fail",
                f"The posting states \"{_excerpt(text, match)}\". {rationale}",
                raw_data={
                    "matched_phrase": match.group(0),
                    "pattern": slug,
                    "excerpt": _excerpt(text, match),
                },
                weight_key=WEIGHT_KEY,
            )
        )

    context["selection_process_flags"] = [e.raw_data["pattern"] for e in evidence if e.raw_data]

    if evidence:
        return evidence
    return [
        item(
            LEVEL, "l3_selection_process", "Recruitment Process Analysis", "pass",
            "The described selection process contains none of the known "
            "instant-selection, no-interview or private-channel patterns.",
            raw_data={"patterns_checked": [slug for slug, _, _, _ in PROCESS_PATTERNS]},
            weight_key=WEIGHT_KEY,
        )
    ]


def _excerpt(text: str, match: re.Match[str]) -> str:
    start = max(0, match.start() - CONTEXT_WINDOW // 2)
    end = min(len(text), match.end() + CONTEXT_WINDOW // 2)
    snippet = " ".join(text[start:end].split())
    return f"...{snippet}..." if start > 0 else snippet
