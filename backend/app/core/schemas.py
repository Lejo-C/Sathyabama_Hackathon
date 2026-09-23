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

from pydantic import BaseModel, Field, model_validator

CheckStatus = Literal["pass", "warning", "fail", "unavailable"]

# How much a check is allowed to matter. The tier decides the points a failed
# check removes, so "why is this posting risky?" always answers in the same
# vocabulary the UI shows the candidate.
Priority = Literal["critical", "high", "medium", "low"]

RiskBand = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


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
    priority: Priority = Field(
        default="medium",
        description="how much this check is allowed to matter",
    )
    points: float = Field(
        default=0.0,
        description="points this item actually removed from its level's score",
    )


class Contributor(BaseModel):
    """One line of the "why is this risky?" breakdown.

    Mirrors the shape the dashboard already renders, so a risk breakdown can be
    bound straight to it.
    """

    check_id: str
    title: str
    level: int
    priority: Priority
    status: CheckStatus
    points: float = Field(description="points removed from the safety score")
    percentage: float = Field(
        ge=0.0, le=100.0, description="share of all risk points raised, 0-100"
    )
    finding: str


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
    risk_score: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="100 - level_score; higher = riskier",
    )
    contributors: list[Contributor] = Field(
        default_factory=list,
        description="what drove this level's score, worst first",
    )
    basis: str = Field(
        default="",
        description="one line stating how this level's score was arrived at",
    )

    @classmethod
    def from_evidence(
        cls,
        level: int,
        evidence: list[EvidenceItem],
        level_score: float,
        contributors: list[Contributor] | None = None,
        basis: str = "",
    ) -> "LevelReport":
        statuses = [item.status for item in evidence]
        external = [item for item in evidence if item.status == "unavailable"]
        score = round(max(0.0, min(100.0, level_score)), 2)
        return cls(
            level=level,
            checks_run=len(evidence),
            checks_passed=statuses.count("pass"),
            checks_failed=statuses.count("fail"),
            checks_warning=statuses.count("warning"),
            checks_unavailable=statuses.count("unavailable"),
            evidence=evidence,
            level_score=score,
            risk_score=round(100.0 - score, 2),
            degraded=bool(evidence) and len(external) == len(evidence),
            contributors=contributors or [],
            basis=basis,
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


class Level1Flag(BaseModel):
    """One signal the Level 1 poster/text analysis raised.

    Field names follow the objects already in the dashboard's mock data, so the
    Level 1 module can hand over what it renders today.
    """

    id: str
    title: str
    severity: Priority | str = Field(
        description='"critical" / "high" / "medium" / "low" (case-insensitive)'
    )
    evidence: str = Field(default="", description="the text that triggered it")
    explanation: str = Field(default="", description="why it matters")
    category: str | None = None
    flagged: bool = True


class Level1Report(BaseModel):
    """What the Level 1 module hands to the final verdict.

    Supply **either** score field, or neither. ``risk_score`` is 0-100 with
    higher = riskier (what the dashboard shows today); ``level_score`` is the
    0-100 safety score the other levels use. With neither, the score is derived
    from the flags by priority, so a partially-built Level 1 still merges.
    """

    level: int = 1
    risk_score: float | None = Field(default=None, ge=0.0, le=100.0)
    level_score: float | None = Field(default=None, ge=0.0, le=100.0)
    flags: list[Level1Flag] = Field(default_factory=list)
    summary: str | None = None

    @classmethod
    def from_dashboard_payload(cls, payload: dict[str, Any]) -> "Level1Report":
        """Accept the shape the dashboard already renders.

        ``mockJobData.js`` carries ``score`` (higher = riskier) and
        ``riskFactors`` with upper-case severities, so the Level 1 module can
        hand over what it builds today without a second mapping step.
        """
        raw_flags = payload.get("riskFactors") or payload.get("flags") or []
        flags = [
            Level1Flag(
                id=str(flag.get("id") or flag.get("check_id") or f"flag_{index}"),
                title=str(flag.get("title") or flag.get("label") or "Level 1 flag"),
                severity=str(flag.get("severity") or "medium"),
                evidence=str(flag.get("evidence") or ""),
                explanation=str(flag.get("explanation") or ""),
                category=flag.get("category"),
                flagged=bool(flag.get("flagged", True)),
            )
            for index, flag in enumerate(raw_flags)
            if isinstance(flag, dict)
        ]
        score = payload.get("score", payload.get("risk_score"))
        summary = payload.get("summary")
        if isinstance(summary, dict):  # the mock nests prose under summary{}
            summary = summary.get("keyThreat") or summary.get("recommendation")
        return cls(
            risk_score=float(score) if isinstance(score, (int, float)) else None,
            level_score=payload.get("level_score"),
            flags=flags,
            summary=summary if isinstance(summary, str) else None,
        )


class FinalVerdict(BaseModel):
    """The single number a candidate sees, and everything behind it."""

    risk_score: float = Field(ge=0.0, le=100.0, description="higher = riskier")
    safety_score: float = Field(
        ge=0.0, le=100.0, description="100 - risk_score, the levels' own direction"
    )
    band: RiskBand
    band_label: str = Field(description='e.g. "HIGH RISK"')
    recommendation: str

    level1: LevelReport | None = None
    level2: LevelReport
    level3: LevelReport
    level4: LevelReport

    contributors: list[Contributor] = Field(
        description="every risk driver across all levels, worst first"
    )
    level_breakdown: list[dict[str, Any]] = Field(
        description="per level: weight, score and share of the final risk"
    )
    weights_used: dict[str, float]
    hard_floors_applied: list[str] = Field(default_factory=list)
    low_confidence: bool = False
    level1_included: bool = False
    summary: str
    explainer_source: Literal["groq", "template"] = "template"
    processing_time_ms: int


class FinalVerdictRequest(BaseModel):
    """Body of POST /api/verify/final."""

    claims: ExtractedClaims
    level1: Level1Report | None = Field(
        default=None,
        description="omit it and the verdict is Levels 2-4 only, clearly marked",
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_dashboard_level1(cls, data: Any) -> Any:
        """Let Level 1 post either this contract or the dashboard's own shape."""
        if isinstance(data, dict):
            level1 = data.get("level1")
            if isinstance(level1, dict) and (
                "riskFactors" in level1 or "flagsCount" in level1
            ):
                converted = Level1Report.from_dashboard_payload(level1)
                data = {**data, "level1": converted}
        return data


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
