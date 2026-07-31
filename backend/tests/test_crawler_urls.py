import ipaddress

import pytest

from geolens_api.crawler.errors import UnsafeUrlError, UrlValidationError
from geolens_api.crawler.urls import PublicUrlValidator, normalize_url
from tests.fixture_site import PUBLIC_FIXTURE_IP, StaticResolver


def test_normalize_url_removes_fragment_default_port_and_dot_segments() -> None:
    normalized = normalize_url("HTTPS://Example.COM.:443/a/../b/%7e?q=%7e#ignored")

    assert normalized.url == "https://example.com/b/~?q=~"
    assert normalized.hostname == "example.com"
    assert normalized.port == 443


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "https://user:password@example.com/",
        "https://example.com:0/",
        "https://example.com/%not-an-escape",
        "http://localhost/",
        "http://api.localhost/",
        "http://127.0.0.1/",
        "http://10.20.30.40/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fd00:ec2::254]/",
        "http://metadata.google.internal/",
    ],
)
def test_normalize_url_rejects_unsafe_or_unsupported_urls(url: str) -> None:
    with pytest.raises(UrlValidationError):
        normalize_url(url)


async def test_validator_rejects_hostname_resolving_to_private_address() -> None:
    resolver = StaticResolver((ipaddress.ip_address("192.168.1.20"),))

    with pytest.raises(UnsafeUrlError, match="not publicly routable"):
        await PublicUrlValidator(resolver).validate("https://fixture.test/")


async def test_validator_rejects_mixed_public_and_private_dns_answers() -> None:
    resolver = StaticResolver(
        (
            PUBLIC_FIXTURE_IP,
            ipaddress.ip_address("127.0.0.1"),
        )
    )

    with pytest.raises(UnsafeUrlError):
        await PublicUrlValidator(resolver).validate("https://fixture.test/")


async def test_validator_pins_and_reuses_public_origin_resolution() -> None:
    resolver = StaticResolver()
    validator = PublicUrlValidator(resolver)

    first = await validator.validate("https://fixture.test/a")
    second = await validator.validate("https://fixture.test/b")

    assert resolver.calls == [("fixture.test", 443)]
    assert first.transport_url == "https://93.184.216.34/a"
    assert second.transport_url == "https://93.184.216.34/b"
    assert first.host_header == "fixture.test"
