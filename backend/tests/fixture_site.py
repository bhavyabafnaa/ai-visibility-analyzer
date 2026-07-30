import ipaddress
from pathlib import Path

import httpx

from geolens_api.crawler.urls import IPAddress

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "crawler"
PUBLIC_FIXTURE_IP = ipaddress.ip_address("93.184.216.34")


class StaticResolver:
    def __init__(self, addresses: tuple[IPAddress, ...] = (PUBLIC_FIXTURE_IP,)) -> None:
        self.addresses = addresses
        self.calls: list[tuple[str, int]] = []

    async def resolve(self, hostname: str, port: int) -> tuple[IPAddress, ...]:
        self.calls.append((hostname, port))
        return self.addresses


class FixtureSite:
    def __init__(self) -> None:
        self.requested_paths: list[str] = []
        self.requested_hosts: list[str] = []

    def response(self, request: httpx.Request) -> httpx.Response:
        self.requested_paths.append(request.url.path)
        self.requested_hosts.append(request.headers["host"])
        if request.headers["host"] != "fixture.test":
            raise AssertionError(f"Unexpected host request: {request.headers['host']}")

        if request.url.path == "/loop-a":
            return httpx.Response(302, headers={"Location": "/loop-b"})
        if request.url.path == "/loop-b":
            return httpx.Response(302, headers={"Location": "/loop-a"})

        filename = "index.html" if request.url.path == "/" else request.url.path.lstrip("/")
        fixture_path = FIXTURE_ROOT / filename
        if not fixture_path.is_file():
            return httpx.Response(404, headers={"Content-Type": "text/plain"})
        content_type = (
            "text/plain"
            if fixture_path.suffix == ".txt"
            else "application/xml"
            if fixture_path.suffix == ".xml"
            else "text/html; charset=utf-8"
        )
        body = fixture_path.read_bytes()
        return httpx.Response(
            200,
            headers={
                "Content-Length": str(len(body)),
                "Content-Type": content_type,
            },
            content=body,
        )

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.response)
