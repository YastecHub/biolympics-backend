"""Celery application + beat schedule for notification jobs."""

from __future__ import annotations

import asyncio

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "biolympics",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
)

celery_app.conf.beat_schedule = {
    "scan-upcoming-fixtures": {
        "task": "app.workers.tasks.scan_upcoming_fixtures",
        "schedule": crontab(minute="*/5"),
    },
    "dispatch-pending-notifications": {
        "task": "app.workers.tasks.dispatch_pending_notifications",
        "schedule": 30.0,
    },
    "prune-stale-subscriptions": {
        "task": "app.workers.tasks.prune_stale_subscriptions",
        "schedule": crontab(hour="3", minute="0"),
    },
}


def run_async(coro):
    """Run an async coroutine from within a synchronous Celery task."""
    return asyncio.run(coro)


# Import tasks so Celery registers them.
from app.workers import tasks  # noqa: E402,F401
