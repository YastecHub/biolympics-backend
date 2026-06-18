"""Public web-push subscription management. No account required."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.api.deps import DbDep
from app.core.config import settings
from app.db.base import utcnow
from app.models.notifications import NotificationPreference, PushSubscription
from app.schemas.push import (
    PublicKeyOut,
    PushSubscriptionCreate,
    PushSubscriptionOut,
    PushSubscriptionUpdate,
    TopicPreference,
)

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/public-key", response_model=PublicKeyOut)
async def public_key() -> PublicKeyOut:
    # Only the PUBLIC VAPID key is ever exposed to clients.
    return PublicKeyOut(public_key=settings.vapid_public_key)


async def _replace_prefs(db: DbDep, sub: PushSubscription, prefs: list[TopicPreference]) -> None:
    await db.execute(
        delete(NotificationPreference).where(NotificationPreference.subscription_id == sub.id)
    )
    for p in prefs:
        db.add(NotificationPreference(subscription_id=sub.id, topic=p.topic, target_id=p.target_id))


@router.post(
    "/subscriptions", response_model=PushSubscriptionOut, status_code=status.HTTP_201_CREATED
)
async def create_subscription(payload: PushSubscriptionCreate, db: DbDep) -> PushSubscriptionOut:
    sub = (
        await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
        )
    ).scalar_one_or_none()
    if sub is None:
        sub = PushSubscription(
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent,
            last_seen_at=utcnow(),
        )
        db.add(sub)
        await db.flush()
    else:
        sub.p256dh = payload.keys.p256dh
        sub.auth = payload.keys.auth
        sub.is_active = True
        sub.last_seen_at = utcnow()

    prefs = payload.preferences or [TopicPreference(topic="ALL")]  # type: ignore[arg-type]
    await _replace_prefs(db, sub, prefs)
    await db.commit()
    await db.refresh(sub)
    return PushSubscriptionOut(id=sub.id, is_active=sub.is_active, preferences=prefs)


@router.patch("/subscriptions/{subscription_id}", response_model=PushSubscriptionOut)
async def update_subscription(
    subscription_id: uuid.UUID, payload: PushSubscriptionUpdate, db: DbDep
) -> PushSubscriptionOut:
    sub = (
        await db.execute(select(PushSubscription).where(PushSubscription.id == subscription_id))
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    await _replace_prefs(db, sub, payload.preferences)
    await db.commit()
    return PushSubscriptionOut(id=sub.id, is_active=sub.is_active, preferences=payload.preferences)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(subscription_id: uuid.UUID, db: DbDep) -> None:
    sub = (
        await db.execute(select(PushSubscription).where(PushSubscription.id == subscription_id))
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    await db.delete(sub)
    await db.commit()
