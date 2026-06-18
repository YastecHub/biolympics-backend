"""Notification fan-out: dedup events and deliver web-push to subscribers.

De-duplication is enforced by a unique ``idempotency_key`` on NotificationEvent,
so the same trigger never produces two events. Score notifications include a
rate-limit window so rapid score changes are grouped rather than spammed.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import utcnow
from app.models.enums import NotificationTopic
from app.models.notifications import (
    NotificationDelivery,
    NotificationEvent,
    NotificationPreference,
    PushSubscription,
)

log = structlog.get_logger("notifications")

SCORE_MIN_INTERVAL = timedelta(seconds=60)


async def create_event(
    db: AsyncSession,
    *,
    idempotency_key: str,
    event_type: str,
    title: str,
    body: str,
    url: str | None = None,
    topic: NotificationTopic = NotificationTopic.ALL,
    target_id: uuid.UUID | None = None,
    is_urgent: bool = False,
    payload: dict | None = None,
) -> NotificationEvent | None:
    """Create a notification event unless an identical key already exists, or a
    recent score event for the same target falls inside the rate-limit window."""
    existing = (
        await db.execute(
            select(NotificationEvent).where(NotificationEvent.idempotency_key == idempotency_key)
        )
    ).scalar_one_or_none()
    if existing:
        return None

    if event_type == "fixture.score_updated" and target_id:
        recent_cutoff = utcnow() - SCORE_MIN_INTERVAL
        recent = (
            await db.execute(
                select(NotificationEvent).where(
                    NotificationEvent.event_type == "fixture.score_updated",
                    NotificationEvent.target_id == target_id,
                    NotificationEvent.created_at >= recent_cutoff,
                )
            )
        ).first()
        if recent:
            log.info("notification.rate_limited", target_id=str(target_id))
            return None

    event = NotificationEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        title=title,
        body=body,
        url=url,
        topic=topic,
        target_id=target_id,
        is_urgent=is_urgent,
        payload=payload or {},
        created_at=utcnow(),
    )
    db.add(event)
    await db.flush()
    return event


async def _matching_subscriptions(
    db: AsyncSession, event: NotificationEvent
) -> list[PushSubscription]:
    """Subscriptions whose preferences match the event's topic/target."""
    stmt = (
        select(PushSubscription)
        .join(
            NotificationPreference,
            NotificationPreference.subscription_id == PushSubscription.id,
        )
        .where(PushSubscription.is_active.is_(True))
    )
    conditions = [NotificationPreference.topic == NotificationTopic.ALL]
    if event.is_urgent:
        conditions.append(NotificationPreference.topic == NotificationTopic.URGENT_ONLY)
    if event.target_id is not None:
        conditions.append(
            (NotificationPreference.topic == event.topic)
            & (NotificationPreference.target_id == event.target_id)
        )
    from sqlalchemy import or_

    stmt = stmt.where(or_(*conditions)).distinct()
    return list((await db.execute(stmt)).scalars().all())


def _send_web_push(
    sub: PushSubscription, event: NotificationEvent
) -> tuple[bool, int | None, str | None]:
    """Best-effort single web-push delivery. Returns (success, status, error)."""
    if not settings.vapid_private_key:
        return False, None, "VAPID not configured"
    try:
        from pywebpush import WebPushException, webpush

        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps({"title": event.title, "body": event.body, "url": event.url}),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True, 201, None
    except WebPushException as exc:  # type: ignore[name-defined]
        status = getattr(exc.response, "status_code", None)
        return False, status, str(exc)[:280]
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)[:280]


async def dispatch_event(db: AsyncSession, event: NotificationEvent) -> dict:
    """Deliver an event to all matching subscriptions; prune dead endpoints."""
    subs = await _matching_subscriptions(db, event)
    sent = failed = 0
    for sub in subs:
        already = (
            await db.execute(
                select(NotificationDelivery).where(
                    NotificationDelivery.event_id == event.id,
                    NotificationDelivery.subscription_id == sub.id,
                )
            )
        ).scalar_one_or_none()
        if already:
            continue
        ok, status_code, error = _send_web_push(sub, event)
        db.add(
            NotificationDelivery(
                event_id=event.id,
                subscription_id=sub.id,
                success=ok,
                status_code=status_code,
                error=error,
                attempted_at=utcnow(),
            )
        )
        if ok:
            sent += 1
        else:
            failed += 1
            if status_code in (404, 410):  # gone — remove invalid subscription
                sub.is_active = False
    event.dispatched_at = datetime.now(UTC)
    await db.commit()
    return {"event_id": str(event.id), "sent": sent, "failed": failed, "total": len(subs)}
