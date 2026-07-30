import ipaddress
import re
from urllib.parse import urlsplit

CITATION_RULE_VERSION = "citation-domain-v1"


def extract_normalized_domain(value: str) -> str | None:
    """Extract a lowercase IDNA hostname, removing only a leading ``www.``."""

    candidate = value.strip()
    if not candidate:
        return None
    scheme_match = re.match(r"^[a-z][a-z0-9+.-]*:", candidate, re.IGNORECASE)
    if scheme_match is not None and not candidate.casefold().startswith(("http://", "https://")):
        return None
    parse_target = (
        candidate if "://" in candidate or candidate.startswith("//") else f"//{candidate}"
    )
    try:
        hostname = urlsplit(parse_target).hostname
    except ValueError:
        return None
    if hostname is None:
        return None

    hostname = hostname.rstrip(".").casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if not hostname:
        return None

    try:
        return ipaddress.ip_address(hostname).compressed
    except ValueError:
        pass

    try:
        normalized = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if any(
        not label
        or len(label) > 63
        or re.fullmatch(r"[a-z0-9-]+", label) is None
        or label.startswith("-")
        or label.endswith("-")
        for label in normalized.split(".")
    ):
        return None
    return normalized


def normalize_citation_domains(urls: list[str]) -> tuple[str, ...]:
    """Return valid citation hostnames in input order, retaining occurrences."""

    domains: list[str] = []
    for url in urls:
        domain = extract_normalized_domain(url)
        if domain is not None:
            domains.append(domain)
    return tuple(domains)


def domain_matches(candidate: str, target: str) -> bool:
    """Return whether candidate is the target hostname or one of its subdomains."""

    normalized_candidate = extract_normalized_domain(candidate)
    normalized_target = extract_normalized_domain(target)
    if normalized_candidate is None or normalized_target is None:
        return False
    return normalized_candidate == normalized_target or normalized_candidate.endswith(
        f".{normalized_target}"
    )
