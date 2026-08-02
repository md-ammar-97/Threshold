"""Celery application and queue definitions. architecture.md §9.1.

A single worker may consume all queues locally; hosted environments can
allocate workers per queue. Task modules register themselves via
`autodiscover_tasks` in later phases as each domain module gains tasks.
"""

from celery import Celery

from instamart_engine.core.config import get_settings

settings = get_settings()

QUEUES = (
    "collection",  # source scraping and ingestion
    "processing",  # cleaning, deduplication, language, privacy
    "ai",  # LLM classifications and synthesis
    "embeddings",  # embedding batches
    "themes",  # clustering, theme metrics, insight generation
    "evaluation",  # gold-sample and grounding evaluations
    "reports",  # export preparation
)

celery_app = Celery(
    "instamart_engine",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_default_queue="processing",
    task_queues={name: {} for name in QUEUES},
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    timezone="UTC",
    enable_utc=True,
)
