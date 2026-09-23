"""Fuzzy comparison helpers for company name vs domain vs location.

Used to catch typosquats ("arnazon.com" standing in for "amazon") and to decide
whether a claimed location is actually corroborated by a page we fetched.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

_NOISE_WORDS = {
    "pvt", "private", "ltd", "limited", "llp", "inc", "incorporated", "corp",
    "corporation", "company", "co", "technologies", "technology", "tech",
    "solutions", "services", "systems", "global", "international", "group",
    "india", "the", "and",
}

_GENERIC_LOCATION_TOKENS = {"remote", "india", "work", "from", "home", "anywhere", "pan"}


def normalise(value: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not value:
        return ""
    return " ".join(re.sub(r"[^a-z0-9\s]+", " ", value.lower()).split())


def core_tokens(name: str | None) -> list[str]:
    """Company name minus legal-suffix and generic noise words."""
    tokens = [t for t in normalise(name).split() if t not in _NOISE_WORDS]
    return tokens or normalise(name).split()


def similarity(left: str | None, right: str | None) -> float:
    """0-100 similarity between two free-text strings."""
    a, b = normalise(left), normalise(right)
    if not a or not b:
        return 0.0
    return float(max(fuzz.token_set_ratio(a, b), fuzz.partial_ratio(a, b)))


def name_matches_domain(company_name: str | None, domain_label: str | None) -> float:
    """Similarity between a company name and the bare domain label.

    ``domain_label`` is the second-level label only ("apexglobal" out of
    "apexglobal.com"), so acronyms and concatenations still score sensibly.
    """
    if not company_name or not domain_label:
        return 0.0

    tokens = core_tokens(company_name)
    label = normalise(domain_label).replace(" ", "")
    if not label:
        return 0.0

    candidates = [
        "".join(tokens),
        " ".join(tokens),
        "".join(t[0] for t in tokens if t),  # acronym, e.g. "tcs"
        normalise(company_name).replace(" ", ""),
    ]
    best = 0.0
    for candidate in candidates:
        if candidate:
            best = max(best, float(fuzz.ratio(candidate, label)))

    # A domain that simply contains every company token is a match even when it
    # carries extra words, e.g. "careers-apexglobal".
    meaningful = [t for t in tokens if len(t) > 2]
    if meaningful and all(t in label for t in meaningful):
        best = max(best, 95.0)
    return best


def contains_location(haystack: str | None, location: str | None) -> bool:
    """True when a meaningful token of ``location`` appears in ``haystack``."""
    text = normalise(haystack)
    if not text or not location:
        return False
    for token in normalise(location).split():
        if len(token) < 4 or token in _GENERIC_LOCATION_TOKENS:
            continue
        if token in text:
            return True
    return False


def meaningful_location_tokens(location: str | None) -> list[str]:
    """Location tokens worth searching for ("remote"/"india" carry no signal)."""
    return [
        token
        for token in normalise(location).split()
        if len(token) >= 4 and token not in _GENERIC_LOCATION_TOKENS
    ]
