from geolens_api.analysis.citations import (
    domain_matches,
    extract_normalized_domain,
    normalize_citation_domains,
)


def test_citation_domain_extraction_normalizes_hostnames() -> None:
    assert extract_normalized_domain("HTTPS://WWW.Example.COM.:443/path?q=1") == "example.com"
    assert extract_normalized_domain("docs.example.com/source") == "docs.example.com"
    assert extract_normalized_domain("https://bücher.example/a") == "xn--bcher-kva.example"


def test_citation_domain_extraction_rejects_non_urls() -> None:
    assert extract_normalized_domain("") is None
    assert extract_normalized_domain("https:///missing-host") is None
    assert extract_normalized_domain("mailto:user@example.com") is None


def test_normalized_citation_domains_retain_valid_occurrences_in_order() -> None:
    assert normalize_citation_domains(
        ["https://www.example.com/a", "not a url", "https://docs.example.com/b"]
    ) == ("example.com", "docs.example.com")


def test_target_domain_matching_includes_subdomains_but_not_suffix_attacks() -> None:
    assert domain_matches("docs.example.com", "https://example.com")
    assert domain_matches("example.com", "www.example.com")
    assert not domain_matches("example.com.attacker.test", "example.com")
