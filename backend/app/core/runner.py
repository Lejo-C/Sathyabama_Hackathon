"""Parallel check runner with per-check isolation.

One rule: a check may fail, hang or explode, and the only consequence is an
``unavailable`` evidence item. It never takes down its siblings and never takes
down the request.
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Callable

from .schemas import CheckStatus, EvidenceItem, ExtractedClaims, Priority
from .scoring import priority_for, weight

logger = logging.getLogger(__name__)

# Every check runs concurrently inside a wave, so this is also the ceiling for
# the wave, and roughly for the whole request. It sits just above the search
# budget: a check whose one external call is a search should get to finish it.
CHECK_TIMEOUT = float(os.getenv("PRAHARI_CHECK_TIMEOUT", "9"))

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
    priority: Priority | None = None,
) -> EvidenceItem:
    """Build an evidence item, pulling weight and priority from the tuning dial.

    ``weight_key`` lets several evidence items share one configured check, e.g.
    every phrase matched by the selection-process analyser.
    """
    key = weight_key or check_id
    return EvidenceItem(
        level=level,
        check_id=check_id,
        label=label,
        status=status,
        finding=finding,
        raw_data=raw_data,
        risk_weight=risk_weight if risk_weight is not None else weight(key),
        confidence=confidence,
        priority=priority or priority_for(key),
    )


def unavailable(
    check: "Check | tuple[int, str, str, float]",
    reason: str,
    check_id: str | None = None,
    label: str | None = None,
) -> EvidenceItem:
    """Build the standard "could not determine" evidence item."""
    if isinstance(check, Check):
        level, cid, lbl, points = check.level, check.check_id, check.label, check.risk_weight
    else:
        level, cid, lbl, points = check
    return EvidenceItem(
        level=level,
        check_id=check_id or cid,
        label=label or lbl,
        status="unavailable",
        finding=f"Could not verify: {reason}.",
        raw_data={"reason": reason},
        risk_weight=points,
        priority=priority_for(check_id or cid),
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

    # One worker per check: they are IO-bound, and a queued check would serialise
    # behind another check's full timeout, which is exactly what a wave exists to
    # avoid.
    results: dict[str, list[EvidenceItem]] = {}
    pool = ThreadPoolExecutor(max_workers=max(1, min(24, len(checks))))
    try:
        futures = {
            pool.submit(_run_one, check, claims, context): check for check in checks
        }
        deadline = time.monotonic() + timeout
        for future, check in futures.items():
            try:
                # One shared deadline, not one per check: waiting `timeout` on
                # each future in turn would make the wave as slow as the sum of
                # its stragglers.
                remaining = max(0.0, deadline - time.monotonic())
                results[check.check_id] = future.result(timeout=remaining)
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
    finally:
        # Do not join: a socket still counting down its own timeout would hold
        # the whole response open long after its result stopped being wanted.
        pool.shutdown(wait=False, cancel_futures=True)

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
