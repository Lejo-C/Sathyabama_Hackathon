"""Recruiter email inspection: free-mail detection and MX validation."""

from __future__ import annotations

import logging
import re

from .domain_utils import parse_domain

logger = logging.getLogger(__name__)

DNS_TIMEOUT = 4.0

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Consumer mailbox providers. A "corporate HR" writing from one of these is a
# documented scam pattern in Indian job-fraud reports.
FREE_MAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in",
    "ymail.com", "rocketmail.com", "outlook.com", "hotmail.com", "live.com",
    "msn.com", "rediffmail.com", "rediff.com", "protonmail.com", "proton.me",
    "zoho.com", "zohomail.com", "aol.com", "gmx.com", "mail.com", "inbox.com",
    "icloud.com", "me.com", "yandex.com", "tutanota.com", "hushmail.com",
}

# Throwaway mailbox services - even stronger signal than consumer webmail.
DISPOSABLE_PROVIDERS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "temp-mail.org", "throwawaymail.com", "yopmail.com", "trashmail.com",
    "sharklasers.com", "getnada.com", "dispostable.com",
}


class DnsUnavailable(RuntimeError):
    """DNS itself could not be reached (offline / blocked resolver)."""


def extract_emails(text: str | None) -> list[str]:
    if not text:
        return []
    seen: list[str] = []
    for match in EMAIL_RE.findall(text):
        lowered = match.lower().rstrip(".")
        if lowered not in seen:
            seen.append(lowered)
    return seen


def email_domain(email: str | None) -> str:
    """Registrable domain of an email address ("hr@mail.acme.co.in" -> "acme.co.in")."""
    if not email or "@" not in email:
        return ""
    return parse_domain(email.strip().lower().rsplit("@", 1)[-1]).registered_domain


def email_host(email: str | None) -> str:
    """Full mail host, subdomain included."""
    if not email or "@" not in email:
        return ""
    return email.strip().lower().rsplit("@", 1)[-1]


def is_free_provider(domain: str | None) -> bool:
    return bool(domain) and domain.lower() in FREE_MAIL_PROVIDERS


def is_disposable_provider(domain: str | None) -> bool:
    return bool(domain) and domain.lower() in DISPOSABLE_PROVIDERS


def has_mx(domain: str, timeout: float = DNS_TIMEOUT) -> bool:
    """True when ``domain`` publishes MX (or fallback A) records for mail.

    Returns ``False`` for a domain that genuinely cannot receive mail.
    Raises ``DnsUnavailable`` when the resolver itself is unreachable, so that
    "we could not check" is never reported as "the domain is fake".
    """
    if not domain:
        return False

    import dns.exception
    import dns.resolver

    resolver = dns.resolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = timeout

    try:
        answers = resolver.resolve(domain, "MX")
        return len(answers) > 0
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        # No MX record. RFC 5321 allows an A record as implicit mail host, so
        # check that before declaring the domain incapable of receiving mail.
        try:
            resolver.resolve(domain, "A")
            return True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return False
        except (dns.exception.Timeout, dns.resolver.NoNameservers) as exc:
            raise DnsUnavailable(f"{type(exc).__name__}: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise DnsUnavailable(f"{type(exc).__name__}: {exc}") from exc
    except (dns.exception.Timeout, dns.resolver.NoNameservers) as exc:
        raise DnsUnavailable(f"{type(exc).__name__}: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise DnsUnavailable(f"{type(exc).__name__}: {exc}") from exc
