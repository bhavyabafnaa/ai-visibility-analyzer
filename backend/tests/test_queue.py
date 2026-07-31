from uuid import uuid4

import pytest

from geolens_api.celery_app import celery_app
from geolens_api.queues import CeleryAnalysisQueue, CeleryCrawlQueue


def test_celery_queue_sends_named_crawl_task(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    class Result:
        id = "celery-result-id"

    def send_task(name: str, *, args: list[str]) -> Result:
        calls.append((name, args))
        return Result()

    monkeypatch.setattr(celery_app, "send_task", send_task)
    crawl_id = uuid4()

    task_id = CeleryCrawlQueue().enqueue(crawl_id)

    assert task_id == "celery-result-id"
    assert calls == [("geolens.crawl_site", [str(crawl_id)])]


def test_celery_queue_sends_named_analysis_task(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    class Result:
        id = "analysis-result-id"

    def send_task(name: str, *, args: list[str]) -> Result:
        calls.append((name, args))
        return Result()

    monkeypatch.setattr(celery_app, "send_task", send_task)
    analysis_id = uuid4()

    task_id = CeleryAnalysisQueue().enqueue(analysis_id)

    assert task_id == "analysis-result-id"
    assert calls == [("geolens.run_analysis", [str(analysis_id)])]
