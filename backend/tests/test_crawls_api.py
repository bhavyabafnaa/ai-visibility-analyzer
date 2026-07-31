from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.crawler.urls import PublicUrlValidator
from geolens_api.database import get_session
from geolens_api.main import app
from geolens_api.models import CrawlJob, CrawlJobStatus
from geolens_api.queues import get_crawl_queue
from geolens_api.routers.crawls import get_url_validator
from tests.fixture_site import StaticResolver


class FakeQueue:
    def __init__(self) -> None:
        self.crawl_ids: list[UUID] = []

    def enqueue(self, crawl_id: UUID) -> str:
        self.crawl_ids.append(crawl_id)
        return f"task-{crawl_id}"


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
async def client(
    session: AsyncSession,
    queue: FakeQueue,
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_crawl_queue] = lambda: queue
    app.dependency_overrides[get_url_validator] = lambda: PublicUrlValidator(StaticResolver())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def create_site(client: AsyncClient, url: str = "https://fixture.test") -> UUID:
    response = await client.post(
        "/projects",
        json={"name": "Crawl API fixture", "site": {"url": url}},
    )
    assert response.status_code == 201
    return UUID(response.json()["site"]["id"])


async def test_create_crawl_queues_job_and_status_endpoint_returns_it(
    client: AsyncClient,
    queue: FakeQueue,
) -> None:
    site_id = await create_site(client)

    created = await client.post(f"/sites/{site_id}/crawls")

    assert created.status_code == 202
    payload = created.json()
    crawl_id = UUID(payload["id"])
    assert payload["site_id"] == str(site_id)
    assert payload["status"] == "pending"
    assert payload["celery_task_id"] == f"task-{crawl_id}"
    assert payload["page_count"] == 0
    assert payload["error_count"] == 0
    assert queue.crawl_ids == [crawl_id]

    status_response = await client.get(f"/crawls/{crawl_id}")
    assert status_response.status_code == 200
    assert status_response.json() == payload


async def test_get_latest_crawl_returns_newest_job_for_requested_site_only(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    first_site_id = await create_site(client)
    second_site_id = await create_site(client, "https://other.fixture.test")
    first = await client.post(f"/sites/{first_site_id}/crawls")
    other_site = await client.post(f"/sites/{second_site_id}/crawls")
    assert first.status_code == other_site.status_code == 202

    first_job = await session.get(CrawlJob, UUID(first.json()["id"]))
    assert first_job is not None
    first_job.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    await session.commit()

    newest = await client.post(f"/sites/{first_site_id}/crawls")
    assert newest.status_code == 202
    newest_job = await session.get(CrawlJob, UUID(newest.json()["id"]))
    assert newest_job is not None
    newest_job.status = CrawlJobStatus.SUCCEEDED
    newest_job.completed_at = datetime.now(timezone.utc)
    newest_job.page_count = 7
    newest_job.error_count = 2
    await session.commit()

    response = await client.get(f"/sites/{first_site_id}/crawls/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == newest.json()["id"]
    assert payload["site_id"] == str(first_site_id)
    assert payload["id"] != other_site.json()["id"]
    assert payload["status"] == "succeeded"
    assert payload["page_count"] == 7
    assert payload["error_count"] == 2


async def test_get_latest_crawl_returns_null_when_site_has_no_crawl(
    client: AsyncClient,
) -> None:
    site_id = await create_site(client)

    response = await client.get(f"/sites/{site_id}/crawls/latest")

    assert response.status_code == 200
    assert response.json() is None


async def test_create_crawl_rejects_private_site_address(
    client: AsyncClient,
    queue: FakeQueue,
) -> None:
    site_id = await create_site(client, "http://127.0.0.1/admin")

    response = await client.post(f"/sites/{site_id}/crawls")

    assert response.status_code == 422
    assert "not publicly routable" in response.json()["detail"]
    assert queue.crawl_ids == []


async def test_create_crawl_returns_404_for_unknown_site(client: AsyncClient) -> None:
    site_id = uuid4()

    response = await client.post(f"/sites/{site_id}/crawls")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Site {site_id} was not found"}


async def test_get_crawl_returns_404_for_unknown_job(client: AsyncClient) -> None:
    crawl_id = uuid4()

    response = await client.get(f"/crawls/{crawl_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Crawl {crawl_id} was not found"}


async def test_queue_failure_is_persisted_and_returns_service_unavailable(
    client: AsyncClient,
) -> None:
    class FailingQueue:
        def enqueue(self, _: UUID) -> str:
            raise RuntimeError("Redis is unavailable")

    site_id = await create_site(client)
    app.dependency_overrides[get_crawl_queue] = FailingQueue

    response = await client.post(f"/sites/{site_id}/crawls")

    assert response.status_code == 503
    assert response.json() == {"detail": "The crawl could not be queued"}
