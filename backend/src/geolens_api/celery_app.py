from celery import Celery  # type: ignore[import-untyped]

from geolens_api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "geolens",
    broker=settings.redis_url_string,
    backend=settings.redis_url_string,
    include=["geolens_api.tasks.analysis", "geolens_api.tasks.crawl"],
)
celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    result_serializer="json",
    task_acks_late=True,
    task_serializer="json",
    task_track_started=True,
    timezone="UTC",
    worker_prefetch_multiplier=1,
)
