from geolens_api.crawler.extractor import extract_html
from tests.fixture_site import FIXTURE_ROOT


def test_extract_html_collects_search_content_and_internal_links() -> None:
    body = (FIXTURE_ROOT / "index.html").read_bytes()

    extracted = extract_html(body, "https://fixture.test/", "fixture.test")

    assert extracted.canonical_url == "https://fixture.test/"
    assert extracted.title == "Fixture home"
    assert extracted.description == "A deterministic local crawler fixture."
    assert extracted.headings == [
        {"level": 1, "text": "Fixture heading"},
        {"level": 2, "text": "Details"},
    ]
    assert "This is the main fixture text." in extracted.main_text
    assert "Header content" not in extracted.main_text
    assert "Footer content" not in extracted.main_text
    assert extracted.structured_data == [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Fixture Site",
        }
    ]
    assert "https://fixture.test/about.html" in extracted.internal_links
    assert not any("outside.example" in link for link in extracted.internal_links)


def test_malformed_html_is_still_extractable() -> None:
    body = (FIXTURE_ROOT / "malformed.html").read_bytes()

    extracted = extract_html(
        body,
        "https://fixture.test/malformed.html",
        "fixture.test",
    )

    assert extracted.title is not None
    assert "Malformed fixture" in extracted.title
    assert extracted.description == "Malformed HTML still extracts."
