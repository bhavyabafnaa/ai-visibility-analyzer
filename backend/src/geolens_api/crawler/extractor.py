import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from geolens_api.crawler.errors import UrlValidationError
from geolens_api.crawler.types import ExtractedPage
from geolens_api.crawler.urls import normalize_url


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _normalized_reference(reference: str, base_url: str) -> str | None:
    try:
        return normalize_url(urljoin(base_url, reference)).url
    except UrlValidationError:
        return None


def _canonical_url(soup: BeautifulSoup, base_url: str) -> str | None:
    for element in soup.find_all("link", href=True):
        if not isinstance(element, Tag):
            continue
        relation = element.get("rel")
        if relation is None:
            relations: list[str] = []
        elif isinstance(relation, str):
            relations = [relation]
        else:
            relations = [str(item) for item in relation]
        if any(str(item).lower() == "canonical" for item in relations):
            href = element.get("href")
            if isinstance(href, str):
                return _normalized_reference(href, base_url)
    return None


def _description(soup: BeautifulSoup) -> str | None:
    fallback: str | None = None
    for element in soup.find_all("meta"):
        if not isinstance(element, Tag):
            continue
        content = element.get("content")
        if not isinstance(content, str):
            continue
        name = element.get("name")
        prop = element.get("property")
        if isinstance(name, str) and name.lower() == "description":
            return _clean_text(content) or None
        if isinstance(prop, str) and prop.lower() == "og:description":
            fallback = _clean_text(content) or None
    return fallback


def _structured_data(soup: BeautifulSoup) -> list[object]:
    results: list[object] = []
    for element in soup.find_all("script"):
        if not isinstance(element, Tag):
            continue
        content_type = element.get("type")
        if not isinstance(content_type, str) or content_type.lower() != "application/ld+json":
            continue
        raw_value = element.string or element.get_text()
        if not raw_value.strip():
            continue
        try:
            results.append(json.loads(raw_value))
        except (json.JSONDecodeError, TypeError):
            continue
    return results


def _internal_links(
    soup: BeautifulSoup,
    base_url: str,
    configured_hostname: str,
) -> list[str]:
    links: set[str] = set()
    for element in soup.find_all("a", href=True):
        if not isinstance(element, Tag):
            continue
        href = element.get("href")
        if not isinstance(href, str):
            continue
        normalized = _normalized_reference(href, base_url)
        if normalized is None:
            continue
        parsed = normalize_url(normalized)
        if parsed.hostname == configured_hostname:
            links.add(parsed.url)
    return sorted(links)


def extract_html(body: bytes, response_url: str, configured_hostname: str) -> ExtractedPage:
    soup = BeautifulSoup(body, "html.parser")
    title = _clean_text(soup.title.get_text()) if soup.title is not None else ""
    headings = [
        {
            "level": int(element.name[1]),
            "text": _clean_text(element.get_text(" ", strip=True)),
        }
        for element in soup.find_all(("h1", "h2", "h3", "h4", "h5", "h6"))
        if isinstance(element, Tag) and _clean_text(element.get_text(" ", strip=True))
    ]
    canonical_url = _canonical_url(soup, response_url)
    description = _description(soup)
    structured_data = _structured_data(soup)
    internal_links = _internal_links(soup, response_url, configured_hostname)

    content_root = soup.find("main") or soup.find("article") or soup.body or soup
    unwanted_elements = (
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
    )
    for unwanted in content_root.find_all(unwanted_elements):
        unwanted.decompose()
    main_text = _clean_text(content_root.get_text(" ", strip=True))

    return ExtractedPage(
        canonical_url=canonical_url,
        title=title or None,
        description=description,
        headings=headings,
        main_text=main_text,
        structured_data=structured_data,
        internal_links=internal_links,
    )
