import re
from dataclasses import dataclass
from urllib import robotparser
from urllib.parse import urljoin

from geolens_api.crawler.errors import UrlValidationError
from geolens_api.crawler.urls import normalize_url

_SITEMAP_DIRECTIVE = re.compile(r"^\s*sitemap\s*:\s*(\S+)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class RobotsPolicy:
    parser: robotparser.RobotFileParser
    sitemap_urls: tuple[str, ...]

    def allows(self, user_agent: str, url: str) -> bool:
        return self.parser.can_fetch(user_agent, url)

    @classmethod
    def allow_all(cls, robots_url: str) -> "RobotsPolicy":
        parser = robotparser.RobotFileParser(robots_url)
        parser.parse([])
        return cls(parser=parser, sitemap_urls=())

    @classmethod
    def disallow_all(cls, robots_url: str) -> "RobotsPolicy":
        parser = robotparser.RobotFileParser(robots_url)
        parser.parse(["User-agent: *", "Disallow: /"])
        return cls(parser=parser, sitemap_urls=())

    @classmethod
    def parse(cls, text: str, robots_url: str) -> "RobotsPolicy":
        parser = robotparser.RobotFileParser(robots_url)
        parser.parse(text.splitlines())
        sitemap_urls: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            match = _SITEMAP_DIRECTIVE.match(line)
            if match is None:
                continue
            try:
                sitemap_url = normalize_url(urljoin(robots_url, match.group(1))).url
            except UrlValidationError:
                continue
            if sitemap_url not in seen:
                sitemap_urls.append(sitemap_url)
                seen.add(sitemap_url)
        return cls(parser=parser, sitemap_urls=tuple(sitemap_urls))
