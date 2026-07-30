from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractedPage:
    canonical_url: str | None
    title: str | None
    description: str | None
    headings: list[dict[str, object]]
    main_text: str
    structured_data: list[object]
    internal_links: list[str]


@dataclass(frozen=True)
class CrawledPage:
    url: str
    canonical_url: str | None
    title: str | None
    description: str | None
    headings: list[dict[str, object]]
    main_text: str
    structured_data: list[object]
    internal_links: list[str]
    content_hash: str
    status_code: int
    depth: int
    content_type: str | None
    response_size: int


@dataclass(frozen=True)
class CrawlFailure:
    url: str | None
    depth: int | None
    stage: str
    error_type: str
    message: str


@dataclass
class CrawlReport:
    pages: list[CrawledPage] = field(default_factory=list)
    errors: list[CrawlFailure] = field(default_factory=list)
    attempted_pages: int = 0
