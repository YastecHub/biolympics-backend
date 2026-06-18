"""Web-push subscription schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import NotificationTopic


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class TopicPreference(BaseModel):
    topic: NotificationTopic
    target_id: uuid.UUID | None = None


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=10)
    keys: PushKeys
    preferences: list[TopicPreference] = Field(default_factory=list)
    user_agent: str | None = None


class PushSubscriptionUpdate(BaseModel):
    preferences: list[TopicPreference]


class PushSubscriptionOut(BaseModel):
    id: uuid.UUID
    is_active: bool
    preferences: list[TopicPreference]


class PublicKeyOut(BaseModel):
    public_key: str
