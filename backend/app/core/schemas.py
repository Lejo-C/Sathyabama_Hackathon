"""Shared contract for the PRAHARI job-fraud detection pipeline.

Every level of the framework speaks this vocabulary:

* ``ExtractedClaims``  - the normalised job posting. Level 1 (poster/text
  analysis, owned by a separate module) produces it; Levels 2-4 consume it.
* ``EvidenceItem``     - one atomic, auditable finding produced by one check.
* ``LevelReport``      - everything one level found, plus its 0-100 score.

Scoring convention used everywhere in this module:
    level_score / combined_score are 0-100 where **lower means riskier**
    (100 = nothing suspicious found, 0 = maximum evidence of fraud).
``combined_risk_score`` is exposed alongside it as ``100 - combined_score``
for UI layers that prefer "higher = riskier".
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["pass", "warning", "fail", "unavailable"]


class ExtractedClaims(BaseModel):
    """What the job posting claims about itself.

    Produced by the Level 1 text-analysis module and handed to Levels 2-4.
    Only ``posting_text`` is mandatory - real postings routinely omit the rest,
    and a missing field is treated as "no evidence", never as evidence of fraud.
    """

    company_name: str | None = None
    job_title: str | None = None
    location: str | None = None
    salary: str | None = None
    recruiter_name: str | None = None
    recruiter_email: str | None = None
    recruiter_phone: str | None = None
    website_url: str | None = None
    posting_text: str
    application_url: str | None = None


class EvidenceItem(BaseModel):
    """One check's verdict, with the raw data that justifies it."""

    level: int = Field(description="2, 3 or 4")
    check_id: str = Field(description='stable id, e.g. "l2_domain_age"')
    label: str = Field(description='human label, e.g. "Domain Age"')
    status: CheckStatus
    finding: str = Field(description="one-line human-readable finding")
    raw_data: dict[str, Any] | None = None
    risk_weight: float = Field(
        description="this check's penalty contribution when it fails"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="0-1; lowered when a lookup only partially succeeded",
    )


class LevelReport(BaseModel):
    """Aggregate result for one level of the framework."""

    level: int
    checks_run: int
    checks_passed: int
    checks_failed: int
    checks_unavailable: int
    evidence: list[EvidenceItem]
    level_score: float = Field(
        ge=0.0, le=100.0, description="0-100 for this level, lower = riskier"
    )
    checks_warning: int = 0
    degraded: bool = Field(
        default=False,
        description="True when every external lookup in this level failed",
    )

    @classmethod
    def from_evidence(
        cls, level: int, evidence: list[EvidenceItem], level_score: float
    ) -> "LevelReport":
        statuses = [item.status for item in evidence]
        external = [item for item in evidence if item.status == "unavailable"]
        return cls(
            level=level,
            checks_run=len(evidence),
            checks_passed=statuses.count("pass"),
            checks_failed=statuses.count("fail"),
            checks_warning=statuses.count("warning"),
            checks_unavailable=statuses.count("unavailable"),
            evidence=evidence,
            level_score=round(max(0.0, min(100.0, level_score)), 2),
            degraded=bool(evidence) and len(external) == len(evidence),
        )


class VerificationResponse(BaseModel):
    """Payload returned by POST /api/verify/company-opportunity."""

    level2: LevelReport
    level3: LevelReport
    level4: LevelReport
    combined_score: float = Field(ge=0.0, le=100.0, description="lower = riskier")
    combined_risk_score: float = Field(
        ge=0.0, le=100.0,
        description="100 - combined_score, for UIs where higher = riskier",
    )
    combined_summary: str
    processing_time_ms: int
    hard_floors_applied: list[str] = Field(default_factory=list)
    low_confidence: bool = Field(
        default=False,
        description="True when external lookups were largely unavailable; "
        "the score then rests on offline rule-based signals only",
    )
    explainer_source: Literal["groq", "template"] = "template"


class DependencyHealth(BaseModel):
    name: str
    available: bool
    detail: str
    latency_ms: int | None = None


class HealthResponse(BaseModel):
    """GET /api/verify/health - live reachability of external dependencies."""

    status: Literal["ok", "degraded"]
    dependencies: list[DependencyHealth]
    checked_at: str
