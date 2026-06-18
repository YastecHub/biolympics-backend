"""Celery tasks: fixture reminders, notification dispatch, subscription cleanup.

Each task runs its async body via ``run_async`` with a fresh DB session.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models.enums import FixtureStatus, NotificationTopic
from app.models.fixtures import Fixture
from app.models.notifications import NotificationEvent, PushSubscription
from app.services.notifications import create_event, dispatch_event
from app.workers.celery_app import celery_app, run_async

# Reminder windows (minutes-before, label) used for idempotency keys.
REMINDER_WINDOWS = [(24 * 60, "24h"), (60, "1h"), (15, "15m")]


async def _scan_upcoming() -> dict:
    created = 0
    async with get_sessionmaker()() as db:
        now = datetime.now(UTC)
        for minutes, label in REMINDER_WINDOWS:
            lo = now + timedelta(minutes=minutes)
            hi = lo + timedelta(minutes=5)  # 5-minute beat granularity
            fixtures = (
                (
                    await db.execute(
                        select(Fixture).where(
                            Fixture.status == FixtureStatus.SCHEDULED,
                            Fixture.scheduled_start >= lo,
                            Fixture.scheduled_start < hi,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for fx in fixtures:
                ev = await create_event(
                    db,
                    idempotency_key=f"reminder:{fx.id}:{label}",
                    event_type="fixture.reminder",
                    title=f"Starting in {label}",
                    body=f"{fx.sport.name} — {fx.round_name or 'fixture'} begins soon.",
                    url=f"/fixtures/{fx.id}",
                    topic=NotificationTopic.SPORT,
                    target_id=fx.sport_id,
                )
                if ev:
                    created += 1
        await db.commit()
    return {"created": created}


async def _dispatch_pending() -> dict:
    results = []
    async with get_sessionmaker()() as db:
        pending = (
            (
                await db.execute(
                    select(NotificationEvent)
                    .where(NotificationEvent.dispatched_at.is_(None))
                    .order_by(NotificationEvent.created_at.asc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        for event in pending:
            results.append(await dispatch_event(db, event))
    return {"dispatched": len(results), "details": results}


async def _prune_stale() -> dict:
    async with get_sessionmaker()() as db:
        stale = (
            (
                await db.execute(
                    select(PushSubscription).where(PushSubscription.is_active.is_(False))
                )
            )
            .scalars()
            .all()
        )
        for sub in stale:
            await db.delete(sub)
        await db.commit()
        return {"pruned": len(stale)}


@celery_app.task(name="app.workers.tasks.scan_upcoming_fixtures")
def scan_upcoming_fixtures() -> dict:
    return run_async(_scan_upcoming())


@celery_app.task(name="app.workers.tasks.dispatch_pending_notifications")
def dispatch_pending_notifications() -> dict:
    return run_async(_dispatch_pending())


@celery_app.task(name="app.workers.tasks.prune_stale_subscriptions")
def prune_stale_subscriptions() -> dict:
    return run_async(_prune_stale())
