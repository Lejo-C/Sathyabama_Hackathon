"""Domain parsing and WHOIS age lookup.

``tldextract`` is pinned to its bundled public-suffix snapshot so that parsing
never needs the network - only the WHOIS lookup itself does, and that one is
wrapped in a hard timeout because port-43 servers love to hang.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timezone

import tldextract

logger = logging.getLogger(__name__)

WHOIS_TIMEOUT = 6.0

# suffix_list_urls=() keeps tldextract on its bundled snapshot: no surprise
# network call the first time a check parses a domain.
_extractor = tldextract.TLDExtract(suffix_list_urls=())


class WhoisUnavailable(RuntimeError):
    """WHOIS could not be reached or returned nothing usable."""


@dataclass
class DomainInfo:
    registered_domain: str
    label: str
    suffix: str
    subdomain: str

    @property
    def is_valid(self) -> bool:
        return bool(self.label and self.suffix)


def parse_domain(url_or_domain: str | None) -> DomainInfo:
    """Extract the registrable domain from a URL, bare domain or email host."""
    if not url_or_domain:
        return DomainInfo("", "", "", "")
    value = url_or_domain.strip()
    if "@" in value and "://" not in value:
        value = value.rsplit("@", 1)[-1]
    parts = _extractor(value)
    registered = ".".join(p for p in (parts.domain, parts.suffix) if p)
    return DomainInfo(
        registered_domain=registered.lower(),
        label=(parts.domain or "").lower(),
        suffix=(parts.suffix or "").lower(),
        subdomain=(parts.subdomain or "").lower(),
    )


def registered_domain(url_or_domain: str | None) -> str:
    return parse_domain(url_or_domain).registered_domain


def _coerce_date(value) -> datetime | None:
    """WHOIS libraries return a datetime, a list of them, or a string."""
    if value is None:
        return None
    if isinstance(value, list):
        candidates = [_coerce_date(item) for item in value]
        candidates = [c for c in candidates if c]
        return min(candidates) if candidates else None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value[: len(fmt) + 2].strip(), fmt).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
    return None


def _raw_whois(domain: str) -> dict:
    import whois  # imported lazily: the module opens sockets at import time

    record = whois.whois(domain)
    return dict(record) if record else {}


def whois_lookup(domain: str, timeout: float = WHOIS_TIMEOUT) -> dict:
    """Run a WHOIS query under a hard timeout.

    Raises ``WhoisUnavailable`` on timeout, network failure or an empty record;
    callers turn that into an ``unavailable`` evidence item.
    """
    if not domain:
        raise WhoisUnavailable("no domain to look up")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            record = pool.submit(_raw_whois, domain).result(timeout=timeout)
    except FutureTimeout as exc:
        raise WhoisUnavailable(f"whois timed out after {timeout}s") from exc
    except Exception as exc:
        raise WhoisUnavailable(f"{type(exc).__name__}: {exc}") from exc

    if not record or not any(record.values()):
        raise WhoisUnavailable("empty whois record")
    return record


@dataclass
class DomainAge:
    domain: str
    created_at: datetime | None
    age_days: int | None
    registrar: str | None
    country: str | None

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "age_days": self.age_days,
            "registrar": self.registrar,
            "country": self.country,
        }


def domain_age(domain: str, timeout: float = WHOIS_TIMEOUT) -> DomainAge:
    """Return creation date and age in days for ``domain``.

    Raises ``WhoisUnavailable`` when the lookup fails outright. A successful
    lookup with no creation date yields ``age_days=None`` - honest "cannot tell"
    rather than a fabricated number.
    """
    record = whois_lookup(domain, timeout=timeout)
    created = _coerce_date(record.get("creation_date") or record.get("created"))
    age_days = None
    if created:
        age_days = max(0, (datetime.now(timezone.utc) - created).days)

    registrar = record.get("registrar")
    country = record.get("country")
    return DomainAge(
        domain=domain,
        created_at=created,
        age_days=age_days,
        registrar=str(registrar) if registrar else None,
        country=str(country) if country else None,
    )
