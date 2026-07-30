import asyncio
import ipaddress
import posixpath
import re
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urlsplit, urlunsplit

from geolens_api.crawler.errors import (
    UnsafeUrlError,
    UrlResolutionError,
    UrlValidationError,
)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
_PERCENT_ESCAPE = re.compile(r"%([0-9a-fA-F]{2})")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_BLOCKED_HOSTS = frozenset(
    {
        "instance-data.ec2.internal",
        "metadata.google.internal",
        "metadata.goog",
    }
)
_METADATA_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("100.100.100.200"),
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("169.254.170.2"),
        ipaddress.ip_address("fd00:ec2::254"),
    }
)


@dataclass(frozen=True)
class NormalizedUrl:
    url: str
    scheme: str
    hostname: str
    port: int
    path: str
    query: str


@dataclass(frozen=True)
class ValidatedUrl:
    normalized: NormalizedUrl
    addresses: tuple[IPAddress, ...]

    @property
    def transport_url(self) -> str:
        address = str(self.addresses[0])
        host = f"[{address}]" if self.addresses[0].version == 6 else address
        default_port = 443 if self.normalized.scheme == "https" else 80
        netloc = host if self.normalized.port == default_port else f"{host}:{self.normalized.port}"
        return urlunsplit(
            (
                self.normalized.scheme,
                netloc,
                self.normalized.path,
                self.normalized.query,
                "",
            )
        )

    @property
    def host_header(self) -> str:
        host = self.normalized.hostname
        if ":" in host:
            host = f"[{host}]"
        default_port = 443 if self.normalized.scheme == "https" else 80
        return host if self.normalized.port == default_port else f"{host}:{self.normalized.port}"


class DnsResolver(Protocol):
    async def resolve(self, hostname: str, port: int) -> tuple[IPAddress, ...]: ...


class SocketDnsResolver:
    async def resolve(self, hostname: str, port: int) -> tuple[IPAddress, ...]:
        loop = asyncio.get_running_loop()
        try:
            records = await loop.getaddrinfo(
                hostname,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        except OSError as error:
            raise UrlResolutionError(f"Could not resolve host {hostname!r}") from error

        addresses = {
            ipaddress.ip_address(record[4][0]) for record in records if record[4] and record[4][0]
        }
        return tuple(sorted(addresses, key=lambda address: (address.version, int(address))))


def _normalize_percent_escapes(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        character = chr(int(match.group(1), 16))
        return character if character in _UNRESERVED else f"%{match.group(1).upper()}"

    return _PERCENT_ESCAPE.sub(replace, value)


def _normalize_path(path: str) -> str:
    normalized = _normalize_percent_escapes(path or "/")
    had_trailing_slash = normalized.endswith("/")
    normalized = posixpath.normpath(normalized)
    if path.startswith("/") and not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if had_trailing_slash and normalized != "/" and not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return quote(normalized, safe="/:@!$&'()*+,;=-._~%")


def _is_blocked_hostname(hostname: str) -> bool:
    return (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname in _BLOCKED_HOSTS
        or any(hostname.endswith(f".{blocked}") for blocked in _BLOCKED_HOSTS)
    )


def _ensure_public_address(address: IPAddress) -> None:
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or address in _METADATA_ADDRESSES
    ):
        raise UnsafeUrlError(f"Address {address} is not publicly routable")


def normalize_url(url: str) -> NormalizedUrl:
    if not isinstance(url, str) or not url.strip():
        raise UrlValidationError("URL must be a non-empty string")
    if any(character in url for character in ("\r", "\n", "\t")):
        raise UrlValidationError("URL contains control characters")

    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
        raw_hostname = parsed.hostname
    except ValueError as error:
        raise UrlValidationError("URL has an invalid host or port") from error

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UrlValidationError("Only HTTP and HTTPS URLs are supported")
    if parsed.username is not None or parsed.password is not None:
        raise UrlValidationError("URLs containing credentials are not supported")
    if raw_hostname is None:
        raise UrlValidationError("URL must include a hostname")
    if _INVALID_PERCENT_ESCAPE.search(parsed.path) or _INVALID_PERCENT_ESCAPE.search(parsed.query):
        raise UrlValidationError("URL contains an invalid percent escape")

    try:
        hostname = raw_hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise UrlValidationError("URL hostname is invalid") from error
    if not hostname or _is_blocked_hostname(hostname):
        raise UnsafeUrlError(f"Hostname {hostname!r} is not allowed")

    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        literal_address = None
    if literal_address is not None:
        _ensure_public_address(literal_address)

    actual_port = port if port is not None else (443 if scheme == "https" else 80)
    if actual_port == 0:
        raise UrlValidationError("URL port must be between 1 and 65535")
    host_for_netloc = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    netloc = host_for_netloc if actual_port == default_port else f"{host_for_netloc}:{actual_port}"
    path = _normalize_path(parsed.path)
    query = quote(
        _normalize_percent_escapes(parsed.query),
        safe="!$&'()*+,-./:;=?@_~%",
    )
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return NormalizedUrl(
        url=normalized,
        scheme=scheme,
        hostname=hostname,
        port=actual_port,
        path=path,
        query=query,
    )


class PublicUrlValidator:
    """Resolve and pin each crawl origin after rejecting every non-public address."""

    def __init__(self, resolver: DnsResolver | None = None) -> None:
        self._resolver = resolver or SocketDnsResolver()
        self._origin_cache: dict[tuple[str, str, int], tuple[IPAddress, ...]] = {}

    async def validate(self, url: str) -> ValidatedUrl:
        normalized = normalize_url(url)
        origin = (normalized.scheme, normalized.hostname, normalized.port)
        addresses = self._origin_cache.get(origin)
        if addresses is None:
            try:
                literal_address = ipaddress.ip_address(normalized.hostname)
            except ValueError:
                addresses = await self._resolver.resolve(
                    normalized.hostname,
                    normalized.port,
                )
            else:
                addresses = (literal_address,)

            if not addresses:
                raise UrlResolutionError(
                    f"Host {normalized.hostname!r} did not resolve to an address"
                )
            for address in addresses:
                _ensure_public_address(address)
            addresses = tuple(
                sorted(set(addresses), key=lambda address: (address.version, int(address)))
            )
            self._origin_cache[origin] = addresses

        return ValidatedUrl(normalized=normalized, addresses=addresses)
