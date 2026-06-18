"""Admin write schemas: fixtures, scoring, lifecycle, announcements."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AnnouncementType, FixtureStatus, MatchEventType


class FixtureCreate(BaseModel):
    sport_id: uuid.UUID
    home_team_id: uuid.UUID | None = None
    away_team_id: uuid.UUID | None = None
    venue_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    score_official_id: uuid.UUID | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    round_name: str | None = None
    match_day: int | None = None
    label: str | None = None
    published: bool = False


class FixtureUpdate(BaseModel):
    venue_id: uuid.UUID | None = None
    score_official_id: uuid.UUID | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    round_name: str | None = None
    match_day: int | None = None
    label: str | None = None
    published: bool | None = None


class ScoreUpdate(BaseModel):
    """Optimistic-concurrency-guarded score update.

    ``expected_version`` must match the fixture's current version or the server
    returns 409 Conflict. ``idempotency_key`` lets a flaky mobile client retry
    safely without double-applying.
    """

    expected_version: int = Field(ge=0)
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)
    home_delta: int | None = None
    away_delta: int | None = None
    period: str | None = None
    clock_text: str | None = None
    home_sets: int | None = Field(default=None, ge=0)
    away_sets: int | None = Field(default=None, ge=0)
    extra: dict | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)


class MatchEventCreate(BaseModel):
    type: MatchEventType
    team_id: uuid.UUID | None = None
    participant_id: uuid.UUID | None = None
    minute: int | None = None
    period: str | None = None
    detail: str | None = None


class PeriodUpdate(BaseModel):
    expected_version: int = Field(ge=0)
    period: str
    current_period_number: int | None = None
    clock_text: str | None = None


class StatusChange(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class CompleteRequest(BaseModel):
    expected_version: int = Field(ge=0)


class CorrectRequest(BaseModel):
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=3, max_length=500)


class RescheduleRequest(BaseModel):
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    venue_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=500)


class GenerateFixturesRequest(BaseModel):
    sport_id: uuid.UUID
    mode: str = Field(description="round_robin | knockout")
    group_id: uuid.UUID | None = None


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    type: AnnouncementType = AnnouncementType.GENERAL
    is_urgent: bool = False
    sport_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    fixture_id: uuid.UUID | None = None
    publish: bool = True
    expires_at: datetime | None = None


class StatusOut(BaseModel):
    status: FixtureStatus
    version: int
    message: str | None = None
