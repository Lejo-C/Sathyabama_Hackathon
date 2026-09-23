"""Parallel check runner with per-check isolation.

One rule: a check may fail, hang or explode, and the only consequence is an
``unavailable`` evidence item. It never takes down its siblings and never takes
down the request.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Callable

from .schemas import CheckStatus, EvidenceItem, ExtractedClaims
from .scoring import weight

logger = logging.getLogger(__name__)

# A single check may legitimately make two 6s external calls (search + fetch),
# so its own ceiling sits above the per-call timeout.
CHECK_TIMEOUT = 20.0

CheckFn = Callable[[ExtractedClaims, dict[str, Any]], list[EvidenceItem]]


@dataclass(frozen=True)
class Check:
    """One registered check: its identity and the callable that runs it."""

    check_id: str
    label: str
    level: int
    risk_weight: float
    fn: CheckFn


def item(
    level: int,
    check_id: str,
    label: str,
    status: CheckStatus,
    finding: str,
    raw_data: dict[str, Any] | None = None,
    confidence: float = 1.0,
    risk_weight: float | None = None,
    weight_key: str | None = None,
) -> EvidenceItem:
    """Build an evidence item, pulling the risk weight from the tuning dial.

    ``weight_key`` lets several evidence items share one configured weight, e.g.
    every phrase matched by the selection-process analyser.
    """
    return EvidenceItem(
        level=level,
        check_id=check_id,
        label=label,
        status=status,
        finding=finding,
        raw_data=raw_data,
        risk_weight=risk_weight if risk_weight is not None else weight(weight_key or check_id),
        confidence=confidence,
    )


def unavailable(
    check: "Check | tuple[int, str, str, float]",
    reason: str,
    check_id: str | None = None,
    label: str | None = None,
) -> EvidenceItem:
    """Build the standard "could not determine" evidence item."""
    if isinstance(check, Check):
        level, cid, lbl, weight = check.level, check.check_id, check.label, check.risk_weight
    else:
        level, cid, lbl, weight = check
    return EvidenceItem(
        level=level,
        check_id=check_id or cid,
        label=label or lbl,
        status="unavailable",
        finding=f"Could not verify: {reason}.",
        raw_data={"reason": reason},
        risk_weight=weight,
        confidence=0.0,
    )


def run_checks(
    checks: list[Check],
    claims: ExtractedClaims,
    context: dict[str, Any],
    timeout: float = CHECK_TIMEOUT,
) -> list[EvidenceItem]:
    """Run every check in parallel and collect their evidence in registry order."""

    if not checks:
        return []

    results: dict[str, list[EvidenceItem]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(checks))) as pool:
        futures = {
            pool.submit(_run_one, check, claims, context): check for check in checks
        }
        for future, check in futures.items():
            try:
                results[check.check_id] = future.result(timeout=timeout)
            except FutureTimeout:
                logger.warning("check %s exceeded %ss", check.check_id, timeout)
                results[check.check_id] = [
                    unavailable(check, f"check timed out after {timeout:.0f}s")
                ]
            except Exception as exc:  # pragma: no cover - _run_one already guards
                logger.exception("check %s crashed", check.check_id)
                results[check.check_id] = [
                    unavailable(check, f"{type(exc).__name__}: {exc}")
                ]

    evidence: list[EvidenceItem] = []
    for check in checks:
        evidence.extend(results.get(check.check_id, []))
    return evidence


def _run_one(
    check: Check, claims: ExtractedClaims, context: dict[str, Any]
) -> list[EvidenceItem]:
    try:
        items = check.fn(claims, context) or []
    except Exception as exc:
        logger.warning("check %s raised %s: %s", check.check_id, type(exc).__name__, exc)
        return [unavailable(check, f"{type(exc).__name__}: {exc}")]
    return list(items)
