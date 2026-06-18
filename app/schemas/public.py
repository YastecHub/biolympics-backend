"""Public read-model response schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    AnnouncementType,
    CompetitionFormat,
    FixtureStatus,
    GenderCategory,
    ScoringType,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TournamentOut(ORMModel):
    id: uuid.UUID
    name: str
    public_brand: str
    slug: str
    timezone: str
    start_date: date | None
    end_date: date | None
    description: str | None
    medal_points: dict


class SportOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    icon: str | None
    description: str | None
    gender_category: GenderCategory
    competition_format: CompetitionFormat
    scoring_type: ScoringType
    requires_table: bool
    requires_bracket: bool
    supports_live: bool
    uses_timing: bool
    periods: int
    display_order: int
    is_active: bool


class DepartmentOut(ORMModel):
    id: uuid.UUID
    name: str
    abbreviation: str
    short_name: str | None
    slug: str
    logo_url: str | None
    primary_color: str
    secondary_color: str
    description: str | None
    contact_person: str | None
    is_active: bool


class VenueOut(ORMModel):
    id: uuid.UUID
    name: str
    address: str | None
    notes: str | None
    is_active: bool


class TeamRef(ORMModel):
    id: uuid.UUID
    department_abbr: str | None = None
    department_name: str | None = None
    display_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None


class LiveStateOut(ORMModel):
    home_score: int
    away_score: int
    period: str | None
    current_period_number: int
    clock_text: str | None
    home_sets: int
    away_sets: int
    status_text: str | None
    extra: dict
    version: int
    last_updated_at: datetime | None


class FixtureOut(BaseModel):
    id: uuid.UUID
    sport_slug: str
    sport_name: str
    status: FixtureStatus
    round_name: str | None
    match_day: int | None
    group_name: str | None = None
    home: TeamRef | None
    away: TeamRef | None
    venue_name: str | None
    venue_tbd: bool
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    time_tbd: bool
    published: bool
    version: int
    live: LiveStateOut | None = None


class StandingRowOut(ORMModel):
    team_id: uuid.UUID
    department_abbr: str | None = None
    department_name: str | None = None
    position: int
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class StandingOut(BaseModel):
    sport_slug: str
    group_name: str | None
    tie_breakers: list[str]
    rows: list[StandingRowOut]


class MedalRowOut(BaseModel):
    department_id: uuid.UUID
    department_abbr: str
    department_name: str
    position: int
    gold: int
    silver: int
    bronze: int
    participation_points: float
    bonus_points: float
    penalties: float
    total_points: float


class AnnouncementOut(ORMModel):
    id: uuid.UUID
    title: str
    body: str
    type: AnnouncementType
    is_urgent: bool
    sport_id: uuid.UUID | None
    department_id: uuid.UUID | None
    fixture_id: uuid.UUID | None
    published_at: datetime | None
    expires_at: datetime | None


class SponsorOut(ORMModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    website_url: str | None
    tier: str | None
    display_order: int


class MatchEventOut(ORMModel):
    id: uuid.UUID
    type: str
    team_id: uuid.UUID | None
    minute: int | None
    period: str | None
    detail: str | None
    created_at: datetime
