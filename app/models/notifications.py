"""Push subscriptions, preferences, notification events, deliveries, templates."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import NotificationTopic


class PushSubscription(UUIDMixin, TimestampMixin, Base):
    """A browser push endpoint. No account required for public users."""

    __tablename__ = "push_subscriptions"

    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreference(UUIDMixin, TimestampMixin, Base):
    """Topic subscription attached to a push subscription."""

    __tablename__ = "notification_preferences"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("push_subscriptions.id", ondelete="CASCADE"), index=True
    )
    topic: Mapped[NotificationTopic] = mapped_column(Enum(NotificationTopic, native_enum=False))
    # Target id for DEPARTMENT/SPORT/FIXTURE topics (null for ALL / URGENT_ONLY).
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    __table_args__ = (UniqueConstraint("subscription_id", "topic", "target_id"),)


class NotificationEvent(UUIDMixin, Base):
    """A notification-worthy event, deduplicated by idempotency_key."""

    __tablename__ = "notification_events"

    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    topic: Mapped[NotificationTopic] = mapped_column(
        Enum(NotificationTopic, native_enum=False), default=NotificationTopic.ALL
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_notification_events_created", "created_at"),)


class NotificationDelivery(UUIDMixin, Base):
    __tablename__ = "notification_deliveries"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_events.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("push_subscriptions.id", ondelete="CASCADE"), index=True
    )
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("event_id", "subscription_id"),)


class NotificationTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notification_templates"

    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title_template: Mapped[str] = mapped_column(String(200))
    body_template: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
