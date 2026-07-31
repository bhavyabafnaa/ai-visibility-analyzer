from typing import Protocol
from uuid import UUID

from geolens_api.celery_app import celery_app


class CrawlQueue(Protocol):
    def enqueue(self, crawl_id: UUID) -> str: ...


class CeleryCrawlQueue:
    def enqueue(self, crawl_id: UUID) -> str:
        result = celery_app.send_task("geolens.crawl_site", args=[str(crawl_id)])
        return str(result.id)


def get_crawl_queue() -> CrawlQueue:
    return CeleryCrawlQueue()
